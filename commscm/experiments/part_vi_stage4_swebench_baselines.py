"""
Part VI Stage 4 — Baselines on SWE-bench Verified–shaped single-edit repair.

Methods: CR-guided, Reward-only, Random, Static heuristic (earliest agent edge).
Architecture-search (GPTSwarm/…) skipped — unfair without shared search space; logged.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from collections import Counter
from pathlib import Path

from credit_assignment import llm as _llm  # noqa: F401
from credit_assignment.fault_injection import FaultInjector, PoisonMode
from commscm.adapters.swebench.extract import swebench_reward_outcome, swebench_state_to_run_trace
from commscm.adapters.swebench.load import load_swebench_verified_subset, offline_fixture_instances
from commscm.adapters.swebench.mechanisms import make_swebench_sticky_registry
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


def _select_edit(prop, *, method: str, report, time_index):
    """Single prune/weaken; never detach terminal sink (C4→C5)."""
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


class StaticHeuristicOperator(PhaseBOperatorBase):
    """
    Harness-local baseline (not a core CCAS change): always rank edges by
    (source time_index ascending) — prefer earliest agent communication edges.
    """

    name = "static_heuristic"

    def propose(self, trace: RunTrace, report: AttributionReport) -> ArchitectureProposal:
        self.ensure_registered(trace)
        events = trace.dag.events
        scored = []
        for src, tgt in dag_edges(trace):
            # Prefer early source; exclude exogenous C0 slightly by boosting agent srcs
            t = float(events[src].time_index)
            bonus = 0.0 if src == "C0" else 10.0
            scored.append((bonus - t, src, tgt))
        scored.sort(key=lambda t: (-t[0], t[1], t[2]))
        edits = self._expand_edge_edits(scored)
        return self._proposal(trace, edits, ["C1"], method=self.name)


def score_trace(tr):
    mechs = make_swebench_sticky_registry(tr.dag)
    return SubsetAttributionEngine(
        DescendantReplayEngine(swebench_reward_outcome, mechs, structural_cost_iters=0),
        AGENT_EVENTS,
        name="SWEBenchCR",
    ).score(tr)


def load_instances(n: int):
    try:
        return load_swebench_verified_subset(n=n, seed=42), "huggingface"
    except Exception as exc:  # noqa: BLE001
        print(f"HF load failed ({exc}); offline fixtures")
        return offline_fixture_instances(min(n, 3)), "offline_fixture"


def run_one(*, instance, mode: PoisonMode, method: str, run_idx: int) -> dict:
    row: dict = {
        "run_idx": run_idx,
        "instance_id": instance.instance_id,
        "task_id": instance.instance_id,
        "poison_mode": mode.value,
        "method": method,
        "framework": "swebench_shaped",
        "n_edits": 0,
        "pipeline_ok": False,
        "extract_ok": False,
        "attribution_ok": False,
        "repair_pipeline_ok": False,
        "failures": [],
    }
    t0 = time.perf_counter()
    try:
        state0 = run_swebench_pipeline(
            instance,
            fault_injector=FaultInjector(mode=mode),
        )
        row["pipeline_ok"] = True
        row["y_before"] = float(state0.global_reward)
        row["sink_valid_before"] = bool((state0.patch_attempt or "").strip())
    except Exception as exc:  # noqa: BLE001
        row["failures"].append({"stage": "pipeline", "error": f"{type(exc).__name__}: {exc}"})
        row["failure_code"] = "F5"
        return row

    if row["y_before"] >= 1.0:
        row["skipped"] = True
        return row

    try:
        tr = swebench_state_to_run_trace(
            state0,
            run_id=f"swe4_{run_idx}_{method}_{mode.value}",
            task_id=instance.instance_id,
        )
        row["extract_ok"] = True
        row["gold"] = tr.gold_fault_event_id
    except Exception as exc:  # noqa: BLE001
        row["failures"].append({"stage": "extract", "error": f"{type(exc).__name__}: {exc}"})
        row["failure_code"] = "F5"
        return row

    try:
        report = score_trace(tr)
        row["attribution_ok"] = True
        row["cr_top1"] = report.predicted_top1
        row["attribution_correct"] = report.predicted_top1 == tr.gold_fault_event_id
    except Exception as exc:  # noqa: BLE001
        row["failures"].append({"stage": "attribution", "error": f"{type(exc).__name__}: {exc}"})
        row["failure_code"] = "F5"
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
        return row

    row["n_edits"] = 1
    row["edit_key"] = f"{edit.kind.value}:{edit.source_event_id}->{edit.target_event_id}"
    row["hit_gold_edge"] = (edit.source_event_id, edit.target_event_id) in gold_harmful_edges(tr)
    if not intervention_supported(edit):
        row["failure_code"] = "F6"
        return row
    iv = edit_to_intervention(edit)
    assert iv is not None

    try:
        state1 = run_swebench_pipeline(
            instance,
            fault_injector=FaultInjector(mode=mode),
            edge_interventions=[iv],
        )
        row["repair_pipeline_ok"] = True
        row["y_after"] = float(state1.global_reward)
        row["sink_valid_after"] = bool((state1.patch_attempt or "").strip())
        row["delta_y"] = row["y_after"] - row["y_before"]
        row["repaired"] = row["y_before"] < 1.0 and row["y_after"] >= 1.0
        row["improved"] = row["y_after"] > row["y_before"]
        row["success"] = (row["repaired"] or row["improved"]) and row["sink_valid_after"]
        row["failure_code"] = classify_failure(
            attribution_ok=True,
            extract_ok=True,
            pipeline_ok=True,
            repair_ok=True,
            attribution_correct=bool(row.get("attribution_correct")),
            hit_gold_edge=bool(row.get("hit_gold_edge")),
            y_before=row["y_before"],
            y_after=row["y_after"],
            sink_valid=bool(row["sink_valid_after"]),
            edit_supported=True,
            n_edits=1,
        )
    except Exception as exc:  # noqa: BLE001
        row["failures"].append({"stage": "repair", "error": f"{type(exc).__name__}: {exc}"})
        row["traceback"] = traceback.format_exc()[-1200:]
        row["failure_code"] = "F5"
    row["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return row


def aggregate(rows: list[dict]) -> dict:
    attempted = [r for r in rows if not r.get("skipped")]
    by_method: dict[str, dict] = {}
    for method in METHODS:
        mrows = [r for r in attempted if r.get("method") == method]
        n = len(mrows)
        repaired = [r for r in mrows if r.get("repaired")]
        scored = [r for r in mrows if r.get("y_after") is not None]
        fail_counts = Counter(r.get("failure_code") for r in mrows if r.get("failure_code"))
        n_rep = len(repaired)
        by_method[method] = {
            "n": n,
            "frac_repaired": n_rep / n if n else 0.0,
            "gold_edge_hit_rate": (
                sum(1 for r in mrows if r.get("hit_gold_edge")) / n if n else 0.0
            ),
            "repair_attribution_precision": (
                sum(1 for r in repaired if r.get("hit_gold_edge")) / n_rep if n_rep else None
            ),
            "mean_delta_y": (
                sum(r.get("delta_y", 0.0) for r in scored) / len(scored) if scored else 0.0
            ),
            "failure_taxonomy": dict(fail_counts),
            "pipeline_ok_rate": (
                sum(1 for r in mrows if r.get("pipeline_ok")) / n if n else 0.0
            ),
        }
    cr = by_method["cr_guided"]
    ro = by_method["reward_only"]
    rnd = by_method["random"]
    st = by_method["static_heuristic"]
    # Prefer gold-pathway precision (H2-lite) over raw repair rate — sink detach blocked.
    gate = (
        cr["n"] > 0
        and cr["pipeline_ok_rate"] >= 0.8
        and cr["frac_repaired"] >= 0.5
        and cr["gold_edge_hit_rate"] > ro["gold_edge_hit_rate"]
        and cr["gold_edge_hit_rate"] > rnd["gold_edge_hit_rate"]
        and cr["gold_edge_hit_rate"] >= st["gold_edge_hit_rate"]
    )
    return {
        "n_attempted_rows": len(attempted),
        "by_method": by_method,
        "stage4_gate_pass": gate,
        "architecture_search_baselines": {
            "applied": False,
            "reason": (
                "GPTSwarm / AgentPrune / G-Designer / MaAS require a different "
                "search/training loop and shared multi-agent search space; "
                "unfair vs single prune/weaken on fixed C0–C5. Documented skip."
            ),
        },
        "core_unchanged": True,
    }


def build_schedule(n_runs: int, instances: list) -> list:
    schedule = []
    i = 0
    while len(schedule) < n_runs:
        method = METHODS[i % len(METHODS)]
        mode = MODES[(i // len(METHODS)) % len(MODES)]
        inst = instances[(i // (len(METHODS) * len(MODES))) % len(instances)]
        schedule.append((inst, mode, method, len(schedule)))
        i += 1
    return schedule


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-runs", type=int, default=36)
    parser.add_argument("--n-instances", type=int, default=6)
    parser.add_argument("--out", type=str, default="results/part_vi_stage4_swebench_baselines.json")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY required")
    os.environ["USE_MOCK_LLM"] = "0"
    os.environ["FAIL_ON_LLM_ERROR"] = "1"

    instances, source = load_instances(args.n_instances)
    rows: list[dict] = []
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    schedule = build_schedule(args.n_runs, instances)
    print(f"Part VI Stage 4 SWE-bench baselines: n_runs={args.n_runs} source={source}")

    for inst, mode, method, idx in schedule:
        print(f"[{idx+1}/{args.n_runs}] {method} {mode.value} {inst.instance_id} ...", flush=True)
        row = run_one(instance=inst, mode=mode, method=method, run_idx=idx)
        rows.append(row)
        if row.get("skipped"):
            print("  skip", flush=True)
        else:
            print(
                f"  y={row.get('y_before')}->{row.get('y_after')} "
                f"repaired={row.get('repaired')} edit={row.get('edit_key')} "
                f"fail={row.get('failure_code')}",
                flush=True,
            )
        if (idx + 1) % 4 == 0 or idx + 1 == args.n_runs:
            summary = aggregate(rows)
            out_path.write_text(
                json.dumps(
                    {
                        "experiment": "part_vi_stage4_swebench_baselines",
                        "partial": idx + 1 < args.n_runs,
                        "instance_source": source,
                        "summary": summary,
                        "rows": rows,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            cr = summary["by_method"]["cr_guided"]
            print(
                f"  checkpoint CR repaired={cr['frac_repaired']:.3f} gate={summary['stage4_gate_pass']}",
                flush=True,
            )

    summary = aggregate(rows)
    payload = {
        "experiment": "part_vi_stage4_swebench_baselines",
        "hypothesis": "H_part_vi CR beats fair baselines on SWE-bench Verified–shaped",
        "instance_source": source,
        "summary": summary,
        "rows": rows,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("\n=== Stage 4 summary ===")
    print(json.dumps(summary, indent=2))
    print(f"gate={'PASS' if summary['stage4_gate_pass'] else 'FAIL'}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
