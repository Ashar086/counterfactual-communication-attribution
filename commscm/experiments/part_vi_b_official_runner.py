"""
Part VI.B — Official SWE-bench Verified evaluation (preregistered H5).

Run exactly as ``PART_VI_B_PREREGISTRATION.md`` (Experiment Frozen 2026-08-02).
Adapter/harness only — no CommSCM core changes.

Primary outcome: official Docker resolve@1 on post-edit patches.
Attribution metrics use injected communication poisons (gold edges) as in Part VI shaped.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import traceback
from collections import Counter
from pathlib import Path

from credit_assignment import llm as _llm  # noqa: F401 — loads .env
from credit_assignment.fault_injection import FaultInjector, PoisonMode
from commscm.adapters.swebench.extract import swebench_reward_outcome, swebench_state_to_run_trace
from commscm.adapters.swebench.load import load_swebench_verified_by_ids
from commscm.adapters.swebench.mechanisms import make_swebench_sticky_registry
from commscm.adapters.swebench.official_eval import (
    evaluate_by_method,
    normalize_model_patch,
    resolve_map_from_report,
)
from commscm.adapters.swebench.pipeline import run_swebench_pipeline
from commscm.attribution.report import AttributionReport
from commscm.attribution.subset import SubsetAttributionEngine
from commscm.ccas.interfaces import ArchitectureEditKind, ArchitectureProposal
from commscm.ccas.operators import (
    CRGuidedOperator,
    PhaseBOperatorBase,
    RandomOperator,
    RewardOnlyOperator,
    dag_edges,
    gold_harmful_edges,
)
from commscm.estimators.replay import DescendantReplayEngine
from commscm.experiments.week6_live_repair import classify_failure
from commscm.schema.events import RunTrace
from commscm.traces.langgraph_live_edit import (
    edit_to_intervention,
    first_prune_or_weaken,
    intervention_supported,
)

AGENT_EVENTS = {"C1", "C2", "C3", "C4", "C5"}
MODES = (PoisonMode.POISON_PLANNER, PoisonMode.POISON_CODER, PoisonMode.POISON_REVIEWER)
METHODS = ("cr_guided", "reward_only", "random", "static_heuristic")

INSTANCE_LIST = Path("results/part_vi_b_instance_list.json")
PROMPT_HASHES = Path("results/part_vi_b_prompt_hashes.json")
DEFAULT_OUT = Path("results/part_vi_b_official.json")
PRED_DIR = Path("results/part_vi_b_predictions")


def _apply_prereg_env() -> None:
    os.environ["USE_MOCK_LLM"] = "0"
    os.environ["FAIL_ON_LLM_ERROR"] = "1"
    os.environ["OPENAI_BASE_MODEL"] = "gpt-4o-mini"
    os.environ["LLM_TEMPERATURE"] = "0.0"
    os.environ["LLM_SEED"] = "42"
    os.environ["OPENAI_TOP_P"] = "1.0"
    os.environ["OPENAI_MAX_TOKENS"] = "4096"
    os.environ["OPENAI_TIMEOUT_SEC"] = "120"


def _verify_prompt_hash() -> None:
    p = Path("commscm/adapters/swebench/pipeline.py")
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    locked = json.loads(PROMPT_HASHES.read_text(encoding="utf-8"))
    expected = locked["files"]["commscm/adapters/swebench/pipeline.py"]
    if digest != expected:
        raise SystemExit(
            f"Prompt hash drift: {digest} != {expected}. "
            "Abort per VI.B freeze (amendment required)."
        )


def _mode_for_instance(instance_id: str) -> PoisonMode:
    h = int(hashlib.sha256(instance_id.encode()).hexdigest()[:8], 16)
    return MODES[h % len(MODES)]


class StaticHeuristicOperator(PhaseBOperatorBase):
    name = "static_heuristic"

    def propose(self, trace: RunTrace, report: AttributionReport) -> ArchitectureProposal:
        self.ensure_registered(trace)
        events = trace.dag.events
        scored = []
        for src, tgt in dag_edges(trace):
            t = float(events[src].time_index)
            bonus = 0.0 if src == "C0" else 10.0
            scored.append((bonus - t, src, tgt))
        scored.sort(key=lambda t: (-t[0], t[1], t[2]))
        edits = self._expand_edge_edits(scored)
        return self._proposal(trace, edits, ["C1"], method=self.name)


def _select_edit(prop, *, method: str, report, time_index):
    filtered = [
        e
        for e in prop.edits
        if not (e.source_event_id == "C4" and e.target_event_id == "C5")
    ]
    if method == "cr_guided":
        return first_prune_or_weaken(
            filtered,
            top1_event=report.predicted_top1,
            target_time_index=time_index,
        )
    for e in filtered:
        if e.kind in (ArchitectureEditKind.PRUNE_EDGE, ArchitectureEditKind.WEAKEN_EDGE):
            if e.source_event_id and e.target_event_id and e.source_event_id != "C0":
                return e
    return first_prune_or_weaken(filtered)


def score_trace(tr):
    mechs = make_swebench_sticky_registry(tr.dag)
    return SubsetAttributionEngine(
        DescendantReplayEngine(swebench_reward_outcome, mechs, structural_cost_iters=0),
        AGENT_EVENTS,
        name="SWEBenchCR",
    ).score(tr)


def run_one(*, instance, mode: PoisonMode, method: str, run_idx: int) -> dict:
    row: dict = {
        "run_idx": run_idx,
        "instance_id": instance.instance_id,
        "poison_mode": mode.value,
        "method": method,
        "framework": "swebench_official_vi_b",
        "n_edits": 0,
        "pipeline_ok": False,
        "extract_ok": False,
        "attribution_ok": False,
        "repair_pipeline_ok": False,
        "resolve_at_1": None,
        "model_patch": "",
        "failures": [],
    }
    t0 = time.perf_counter()
    try:
        state0 = run_swebench_pipeline(
            instance,
            fault_injector=FaultInjector(mode=mode),
            model="gpt-4o-mini",
        )
        row["pipeline_ok"] = True
        row["y_proxy_before"] = float(state0.global_reward)
        row["llm_model"] = (state0.trace_log.get("coder") or {}).get("model")
    except Exception as exc:  # noqa: BLE001
        row["failures"].append({"stage": "pipeline", "error": f"{type(exc).__name__}: {exc}"})
        row["failure_code"] = "F5"
        row["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return row

    try:
        tr = swebench_state_to_run_trace(
            state0,
            run_id=f"vib_{run_idx}_{method}_{mode.value}",
            task_id=instance.instance_id,
        )
        row["extract_ok"] = True
        row["gold"] = tr.gold_fault_event_id
    except Exception as exc:  # noqa: BLE001
        row["failures"].append({"stage": "extract", "error": f"{type(exc).__name__}: {exc}"})
        row["failure_code"] = "F5"
        row["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return row

    try:
        report = score_trace(tr)
        row["attribution_ok"] = True
        row["cr_top1"] = report.predicted_top1
        row["attribution_correct"] = report.predicted_top1 == tr.gold_fault_event_id
        row["p_at_1"] = 1.0 if row["attribution_correct"] else 0.0
    except Exception as exc:  # noqa: BLE001
        row["failures"].append({"stage": "attribution", "error": f"{type(exc).__name__}: {exc}"})
        row["failure_code"] = "F5"
        row["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return row

    if method == "cr_guided":
        op = CRGuidedOperator()
    elif method == "reward_only":
        op = RewardOnlyOperator()
    elif method == "static_heuristic":
        op = StaticHeuristicOperator()
    else:
        op = RandomOperator(seed=run_idx)

    prop = op.propose(tr, report)
    time_index = {eid: ev.time_index for eid, ev in tr.dag.events.items()}
    edit = _select_edit(prop, method=method, report=report, time_index=time_index)
    if edit is None:
        row["failure_code"] = "F6"
        row["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return row

    row["n_edits"] = 1
    row["edit_key"] = f"{edit.kind.value}:{edit.source_event_id}->{edit.target_event_id}"
    row["hit_gold_edge"] = (edit.source_event_id, edit.target_event_id) in gold_harmful_edges(tr)
    if not intervention_supported(edit):
        row["failure_code"] = "F6"
        row["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return row
    iv = edit_to_intervention(edit)
    assert iv is not None

    try:
        state1 = run_swebench_pipeline(
            instance,
            fault_injector=FaultInjector(mode=mode),
            edge_interventions=[iv],
            model="gpt-4o-mini",
        )
        row["repair_pipeline_ok"] = True
        row["y_proxy_after"] = float(state1.global_reward)
        row["model_patch"] = state1.patch_attempt or ""
        row["delta_y_proxy"] = row["y_proxy_after"] - row["y_proxy_before"]
        row["failure_code"] = classify_failure(
            attribution_ok=True,
            extract_ok=True,
            pipeline_ok=True,
            repair_ok=True,
            attribution_correct=bool(row.get("attribution_correct")),
            hit_gold_edge=bool(row.get("hit_gold_edge")),
            y_before=row["y_proxy_before"],
            y_after=row["y_proxy_after"],
            sink_valid=bool((state1.patch_attempt or "").strip()),
            edit_supported=True,
            n_edits=1,
        )
    except Exception as exc:  # noqa: BLE001
        row["failures"].append({"stage": "repair", "error": f"{type(exc).__name__}: {exc}"})
        row["traceback"] = traceback.format_exc()[-1200:]
        row["failure_code"] = "F5"
    row["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return row


def build_schedule(instances: list, methods: list[str]) -> list:
    schedule = []
    idx = 0
    for inst in instances:
        mode = _mode_for_instance(inst.instance_id)
        for method in methods:
            schedule.append((inst, mode, method, idx))
            idx += 1
    return schedule


def _checkpoint(path: Path, rows: list, *, partial: bool, meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({**meta, "partial": partial, "rows": rows}, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Part VI.B official SWE-bench Verified")
    parser.add_argument("--limit", type=int, default=0, help="Limit instances (0=all 100)")
    parser.add_argument("--methods", type=str, default=",".join(METHODS))
    parser.add_argument("--out", type=str, default=str(DEFAULT_OUT))
    parser.add_argument("--skip-docker", action="store_true", help="LLM+CR only; defer resolve@1")
    parser.add_argument(
        "--docker-only",
        action="store_true",
        help="Re-score existing checkpoint patches with fixed per-method Docker eval",
    )
    parser.add_argument(
        "--docker-every",
        type=int,
        default=8,
        help="Accumulate this many new patches before a Docker flush (LLM mode)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="SWE-bench harness parallelism (prereg does not lock this; free wall-clock)",
    )
    args = parser.parse_args()

    _apply_prereg_env()
    if not args.docker_only and not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY required (via .env)")
    if not args.docker_only:
        _verify_prompt_hash()

    listing = json.loads(INSTANCE_LIST.read_text(encoding="utf-8"))
    ids = list(listing["instance_ids"])
    if args.limit and args.limit > 0:
        ids = ids[: args.limit]

    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    out_path = Path(args.out)
    meta = {
        "experiment": "part_vi_b_official",
        "hypothesis": "H5",
        "prereg": "PART_VI_B_PREREGISTRATION.md",
        "instance_list": str(INSTANCE_LIST),
        "n_instances": len(ids),
        "methods": methods,
        "core_unchanged": True,
        "harness_note": (
            "Docker eval runs one method per predictions file "
            "(swebench collapses by instance_id; last-wins bug)."
        ),
        "max_workers": args.max_workers,
    }

    if args.docker_only:
        if not out_path.exists():
            raise SystemExit(f"Missing checkpoint {out_path}")
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        rows = list(payload.get("rows") or [])
        pending = []
        for r in rows:
            if not (r.get("model_patch") or "").strip():
                continue
            pending.append(
                {
                    "instance_id": r["instance_id"],
                    "model_name_or_path": f"commscm-vi-b-{r['method']}",
                    "model_patch": normalize_model_patch(r["model_patch"]),
                }
            )
        print(
            f"Docker-only rescore: n_preds={len(pending)} workers={args.max_workers}",
            flush=True,
        )
        # Chunk by unique instances to bound memory; still one method file each
        results = evaluate_by_method(
            pending,
            run_id_prefix=f"vi_b_rescore_{out_path.stem}",
            pred_dir=PRED_DIR,
            max_workers=args.max_workers,
            timeout=1800,
            namespace="swebench",
        )
        for r in rows:
            ev = results.get(r["method"])
            if not ev:
                continue
            rmap = ev.get("resolve_map") or resolve_map_from_report(ev.get("report"))
            if r["instance_id"] in rmap:
                r["resolve_at_1"] = 1.0 if rmap[r["instance_id"]] else 0.0
            r["docker_run_id"] = ev.get("run_id")
            r["docker_eval"] = {
                "returncode": ev.get("returncode"),
                "resolved_known": r["instance_id"] in rmap,
                "rescore": True,
            }
        meta = {**payload, **meta, "partial": True, "docker_rescored": True}
        _checkpoint(out_path, rows, partial=True, meta=meta)
        print(f"Wrote rescored {out_path}", flush=True)
        return

    print(f"VI.B loading {len(ids)} instances (no truncate)...", flush=True)
    instances = load_swebench_verified_by_ids(ids, truncate_problem=False)
    schedule = build_schedule(instances, methods)

    rows: list[dict] = []
    if out_path.exists():
        prev = json.loads(out_path.read_text(encoding="utf-8"))
        rows = list(prev.get("rows") or [])
        done = {(r["instance_id"], r["method"]) for r in rows}
        schedule = [s for s in schedule if (s[0].instance_id, s[2]) not in done]
        print(f"Resuming: {len(rows)} done, {len(schedule)} remaining", flush=True)

    pending_preds: list[dict[str, str]] = []
    batch_i = 0

    def flush_docker(force: bool = False) -> None:
        nonlocal batch_i, pending_preds, rows
        if args.skip_docker or not pending_preds:
            return
        if not force and len(pending_preds) < args.docker_every:
            return
        batch_i += 1
        run_id_prefix = f"vi_b_{out_path.stem}_{batch_i}"
        print(
            f"  Docker flush batch {batch_i} n={len(pending_preds)} "
            f"(per-method files, workers={args.max_workers})",
            flush=True,
        )
        results = evaluate_by_method(
            pending_preds,
            run_id_prefix=run_id_prefix,
            pred_dir=PRED_DIR,
            max_workers=args.max_workers,
            timeout=1800,
            namespace="swebench",
        )
        for r in rows:
            ev = results.get(r["method"])
            if not ev:
                continue
            # only update rows that were in this pending set
            pending_ids = {
                p["instance_id"]
                for p in pending_preds
                if p["model_name_or_path"].endswith(r["method"])
            }
            if r["instance_id"] not in pending_ids:
                continue
            rmap = ev.get("resolve_map") or resolve_map_from_report(ev.get("report"))
            if r["instance_id"] in rmap:
                r["resolve_at_1"] = 1.0 if rmap[r["instance_id"]] else 0.0
            r["docker_run_id"] = ev.get("run_id")
            r["docker_eval"] = {
                "returncode": ev.get("returncode"),
                "resolved_known": r["instance_id"] in rmap,
            }
        pending_preds = []
        _checkpoint(out_path, rows, partial=True, meta=meta)

    print(
        f"Part VI.B official: schedule={len(schedule)} skip_docker={args.skip_docker} "
        f"workers={args.max_workers}",
        flush=True,
    )
    for inst, mode, method, idx in schedule:
        print(f"[{len(rows)+1}] {method} {mode.value} {inst.instance_id} ...", flush=True)
        row = run_one(instance=inst, mode=mode, method=method, run_idx=len(rows))
        rows.append(row)
        print(
            f"  proxy={row.get('y_proxy_before')}->{row.get('y_proxy_after')} "
            f"gold_edge={row.get('hit_gold_edge')} p@1={row.get('p_at_1')} "
            f"fail={row.get('failure_code')}",
            flush=True,
        )
        if row.get("model_patch"):
            pending_preds.append(
                {
                    "instance_id": row["instance_id"],
                    "model_name_or_path": f"commscm-vi-b-{method}",
                    "model_patch": row["model_patch"],
                }
            )
        _checkpoint(out_path, rows, partial=True, meta=meta)
        flush_docker(force=False)

    flush_docker(force=True)
    _checkpoint(out_path, rows, partial=False, meta=meta)
    print(f"Wrote {out_path} n_rows={len(rows)}", flush=True)
    print("Next: python -m commscm.experiments.part_vi_b_analyze", flush=True)


if __name__ == "__main__":
    main()
