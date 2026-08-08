"""
Part V Stage 4 — Single-edit repair on AutoGen (Week-6 pipeline).

Only after Stages 2–3 attribution hold. Adapter-only edge gating.
No verifier. No iterative CCAS. Frozen CR / operators.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from collections import Counter
from pathlib import Path

from credit_assignment.fault_injection import FaultInjector, PoisonMode
from credit_assignment.tasks import load_tasks
from credit_assignment import llm as _llm  # noqa: F401
from commscm.adapters.autogen.extract import autogen_reward_outcome, autogen_state_to_run_trace
from commscm.adapters.autogen.mechanisms import make_autogen_sticky_registry
from commscm.adapters.autogen.pipeline import run_autogen_pipeline
from commscm.attribution.subset import SubsetAttributionEngine
from commscm.ccas.operators import (
    CRGuidedOperator,
    RandomOperator,
    RewardOnlyOperator,
    gold_harmful_edges,
)
from commscm.estimators.replay import DescendantReplayEngine
from commscm.experiments.week6_live_repair import classify_failure
from commscm.traces.langgraph_live_edit import (
    edit_to_intervention,
    first_prune_or_weaken,
    intervention_supported,
)

AGENT_EVENTS = {"C1", "C2", "C3", "C4", "C5"}
MODES = (PoisonMode.POISON_PLANNER, PoisonMode.POISON_CODER, PoisonMode.POISON_REVIEWER)
METHODS = ("cr_guided", "reward_only", "random")


def score_trace(tr):
    mechs = make_autogen_sticky_registry(tr.dag)
    return SubsetAttributionEngine(
        DescendantReplayEngine(autogen_reward_outcome, mechs, structural_cost_iters=0),
        AGENT_EVENTS,
        name="AutoGenCR",
    ).score(tr)


def run_one(*, task, mode: PoisonMode, method: str, run_idx: int) -> dict:
    row: dict = {
        "run_idx": run_idx,
        "task_id": task.task_id,
        "poison_mode": mode.value,
        "method": method,
        "framework": "autogen_agentchat",
        "n_edits": 0,
        "pipeline_ok": False,
        "extract_ok": False,
        "attribution_ok": False,
        "repair_pipeline_ok": False,
        "failures": [],
    }
    t0 = time.perf_counter()
    try:
        state0 = run_autogen_pipeline(
            task.prompt,
            fault_injector=FaultInjector(mode=mode),
            entry_point=task.entry_point,
            test_cases=list(task.test_cases),
            reference_solution=task.reference_solution,
        )
        row["pipeline_ok"] = True
        row["y_before"] = float(state0.global_reward)
        row["sink_valid_before"] = bool((state0.code or "").strip())
    except Exception as exc:  # noqa: BLE001
        row["failures"].append({"stage": "pipeline", "error": f"{type(exc).__name__}: {exc}"})
        row["failure_code"] = "F5"
        return row

    if row["y_before"] >= 1.0:
        row["skipped"] = True
        return row

    try:
        tr = autogen_state_to_run_trace(
            state0, run_id=f"ag4_{run_idx}_{method}_{mode.value}", task_id=task.task_id
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
    else:
        op = RandomOperator(seed=run_idx)

    prop = op.propose(tr, report)
    time_index = {eid: ev.time_index for eid, ev in tr.dag.events.items()}
    top1_for_action = report.predicted_top1 if method == "cr_guided" else None
    if method != "cr_guided" and prop.motivating_event_ids:
        top1_for_action = prop.motivating_event_ids[0]
    edit = first_prune_or_weaken(
        prop.edits,
        top1_event=top1_for_action,
        target_time_index=time_index if method == "cr_guided" else None,
    )
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
        state1 = run_autogen_pipeline(
            task.prompt,
            fault_injector=FaultInjector(mode=mode),
            entry_point=task.entry_point,
            test_cases=list(task.test_cases),
            reference_solution=task.reference_solution,
            edge_interventions=[iv],
        )
        row["repair_pipeline_ok"] = True
        row["y_after"] = float(state1.global_reward)
        row["sink_valid_after"] = bool((state1.code or "").strip())
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
    cr, ro, rnd = by_method["cr_guided"], by_method["reward_only"], by_method["random"]
    gate = (
        cr["n"] > 0
        and cr["pipeline_ok_rate"] >= 0.9
        and cr["frac_repaired"] > ro["frac_repaired"]
        and cr["frac_repaired"] > rnd["frac_repaired"]
    )
    return {
        "n_attempted_rows": len(attempted),
        "by_method": by_method,
        "stage4_gate_pass": gate,
        "core_unchanged": True,
    }


def build_schedule(n_runs: int, tasks: list) -> list:
    schedule = []
    i = 0
    while len(schedule) < n_runs:
        method = METHODS[i % len(METHODS)]
        mode = MODES[(i // len(METHODS)) % len(MODES)]
        task = tasks[(i // (len(METHODS) * len(MODES))) % len(tasks)]
        schedule.append((task, mode, method, len(schedule)))
        i += 1
    return schedule


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-runs", type=int, default=30)
    parser.add_argument("--out", type=str, default="results/part_v_stage4_autogen_repair.json")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY required")
    os.environ["USE_MOCK_LLM"] = "0"
    os.environ["FAIL_ON_LLM_ERROR"] = "1"

    tasks = load_tasks()
    rows: list[dict] = []
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    schedule = build_schedule(args.n_runs, tasks)
    print(f"Part V Stage 4 AutoGen single-edit repair: n_runs={args.n_runs}")

    for task, mode, method, idx in schedule:
        print(f"[{idx+1}/{args.n_runs}] {method} {mode.value} {task.task_id} ...", flush=True)
        row = run_one(task=task, mode=mode, method=method, run_idx=idx)
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
        if (idx + 1) % 3 == 0 or idx + 1 == args.n_runs:
            summary = aggregate(rows)
            out_path.write_text(
                json.dumps(
                    {
                        "experiment": "part_v_stage4_autogen_repair",
                        "partial": idx + 1 < args.n_runs,
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
        "experiment": "part_v_stage4_autogen_repair",
        "hypothesis": "H4 single-edit repair transfers adapter-only",
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
