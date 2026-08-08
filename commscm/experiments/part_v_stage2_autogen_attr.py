"""
Part V Stage 2 — Attribution invariance on AutoGen (no repair).

Same poison modes as LangGraph Week 5. Measures P@1, Gold Hit, confidence,
Attribution Stability hooks. Frozen CR engine; adapter-only.
"""

from __future__ import annotations

import argparse
import json
import os
import traceback
from pathlib import Path

from credit_assignment.fault_injection import FaultInjector, PoisonMode
from credit_assignment.tasks import load_tasks
from credit_assignment import llm as _llm  # noqa: F401
from commscm.adapters.autogen.extract import autogen_reward_outcome, autogen_state_to_run_trace
from commscm.adapters.autogen.mechanisms import make_autogen_sticky_registry
from commscm.adapters.autogen.pipeline import run_autogen_pipeline
from commscm.attribution.subset import SubsetAttributionEngine
from commscm.estimators.replay import DescendantReplayEngine

AGENT_EVENTS = {"C1", "C2", "C3", "C4", "C5"}
MODES = (PoisonMode.POISON_PLANNER, PoisonMode.POISON_CODER, PoisonMode.POISON_REVIEWER)


def score_trace(tr):
    mechs = make_autogen_sticky_registry(tr.dag)
    return SubsetAttributionEngine(
        DescendantReplayEngine(autogen_reward_outcome, mechs, structural_cost_iters=0),
        AGENT_EVENTS,
        name="AutoGenCR",
    ).score(tr)


def _reward_only_top1(rows: list) -> str | None:
    if not rows:
        return None
    return sorted(rows, key=lambda r: r.event_id, reverse=True)[0].event_id


def _random_top1(rows: list, seed: int) -> str | None:
    import random

    ids = [r.event_id for r in rows]
    return random.Random(seed).choice(ids) if ids else None


def _confidence(rows: list) -> float | None:
    if len(rows) < 2:
        return None
    ordered = sorted(rows, key=lambda r: (-r.delta_y, r.event_id))
    return float(ordered[0].delta_y - ordered[1].delta_y)


def run_one(*, task, mode: PoisonMode, run_idx: int) -> dict:
    row: dict = {
        "run_idx": run_idx,
        "task_id": task.task_id,
        "poison_mode": mode.value,
        "framework": "autogen_agentchat",
        "pipeline_ok": False,
        "extract_ok": False,
        "attribution_ok": False,
        "failures": [],
    }
    try:
        state = run_autogen_pipeline(
            task.prompt,
            fault_injector=FaultInjector(mode=mode),
            entry_point=task.entry_point,
            test_cases=list(task.test_cases),
            reference_solution=task.reference_solution,
        )
        row["pipeline_ok"] = True
        row["global_reward"] = float(state.global_reward)
        row["poisoned_node"] = state.poisoned_node
    except Exception as exc:  # noqa: BLE001
        row["failures"].append({"stage": "pipeline", "error": f"{type(exc).__name__}: {exc}"})
        row["traceback"] = traceback.format_exc()[-1500:]
        return row

    try:
        tr = autogen_state_to_run_trace(
            state, run_id=f"ag_{run_idx}_{mode.value}_{task.task_id}", task_id=task.task_id
        )
        row["extract_ok"] = True
        row["gold"] = tr.gold_fault_event_id
        row["n_events"] = len(tr.dag.events)
    except Exception as exc:  # noqa: BLE001
        row["failures"].append({"stage": "extract", "error": f"{type(exc).__name__}: {exc}"})
        return row

    try:
        report = score_trace(tr)
        ordered = sorted(report.rows, key=lambda r: (-r.delta_y, r.event_id))
        row["attribution_ok"] = True
        row["cr_top1"] = report.predicted_top1
        row["cr_ranking"] = [r.event_id for r in ordered]
        row["reward_only_top1"] = _reward_only_top1(report.rows)
        row["random_top1"] = _random_top1(report.rows, seed=run_idx)
        row["cr_hit"] = report.predicted_top1 == tr.gold_fault_event_id
        row["reward_only_hit"] = row["reward_only_top1"] == tr.gold_fault_event_id
        row["random_hit"] = row["random_top1"] == tr.gold_fault_event_id
        row["confidence_gap"] = _confidence(report.rows)
    except Exception as exc:  # noqa: BLE001
        row["failures"].append(
            {"stage": "attribution", "error": f"{type(exc).__name__}: {exc}"}
        )
        row["traceback"] = traceback.format_exc()[-1500:]
    return row


def aggregate(rows: list[dict]) -> dict:
    scored = [r for r in rows if r.get("attribution_ok")]
    n = len(scored)

    def rate(key: str) -> float:
        return sum(1 for r in scored if r.get(key)) / n if n else 0.0

    fail_stages: dict[str, int] = {}
    for r in rows:
        for f in r.get("failures") or []:
            fail_stages[f["stage"]] = fail_stages.get(f["stage"], 0) + 1

    by_mode: dict[str, dict] = {}
    for mode in MODES:
        subset = [r for r in scored if r["poison_mode"] == mode.value]
        m = len(subset)
        by_mode[mode.value] = {
            "n": m,
            "cr_p_at_1": sum(1 for r in subset if r.get("cr_hit")) / m if m else 0.0,
            "reward_only_p_at_1": (
                sum(1 for r in subset if r.get("reward_only_hit")) / m if m else 0.0
            ),
            "random_p_at_1": sum(1 for r in subset if r.get("random_hit")) / m if m else 0.0,
        }

    return {
        "n_attempted": len(rows),
        "n_scored": n,
        "pipeline_ok_rate": sum(1 for r in rows if r.get("pipeline_ok")) / len(rows) if rows else 0.0,
        "extract_ok_rate": sum(1 for r in rows if r.get("extract_ok")) / len(rows) if rows else 0.0,
        "attribution_ok_rate": n / len(rows) if rows else 0.0,
        "cr_p_at_1": rate("cr_hit"),
        "reward_only_p_at_1": rate("reward_only_hit"),
        "random_p_at_1": rate("random_hit"),
        "mean_confidence_gap": (
            sum(r["confidence_gap"] for r in scored if r.get("confidence_gap") is not None)
            / max(1, sum(1 for r in scored if r.get("confidence_gap") is not None))
        ),
        "failure_counts_by_stage": fail_stages,
        "by_poison_mode": by_mode,
        "stage2_gate_pass": (
            n > 0 and rate("cr_hit") > rate("reward_only_hit") and rate("cr_hit") > rate("random_hit")
        ),
        "core_unchanged": True,
    }


def build_schedule(n_runs: int, tasks: list) -> list:
    schedule = []
    i = 0
    while len(schedule) < n_runs:
        task = tasks[i % len(tasks)]
        mode = MODES[i % len(MODES)]
        schedule.append((task, mode, len(schedule)))
        i += 1
    return schedule


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-runs", type=int, default=30)
    parser.add_argument("--out", type=str, default="results/part_v_stage2_autogen_attr.json")
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
    print(f"Part V Stage 2 AutoGen attribution: n_runs={args.n_runs}")
    print("Core Invariance Principle: adapter-only; no Part I–III changes.")

    for task, mode, idx in schedule:
        print(f"[{idx+1}/{args.n_runs}] {mode.value} task={task.task_id} ...", flush=True)
        row = run_one(task=task, mode=mode, run_idx=idx)
        rows.append(row)
        print(
            f"  cr_top1={row.get('cr_top1')} gold={row.get('gold')} hit={row.get('cr_hit')} "
            f"y={row.get('global_reward')}",
            flush=True,
        )
        if (idx + 1) % 5 == 0 or idx + 1 == args.n_runs:
            summary = aggregate(rows)
            out_path.write_text(
                json.dumps(
                    {
                        "experiment": "part_v_stage2_autogen_attribution",
                        "partial": idx + 1 < args.n_runs,
                        "summary": summary,
                        "rows": rows,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(
                f"  checkpoint CR P@1={summary['cr_p_at_1']:.3f} "
                f"gate={summary['stage2_gate_pass']}",
                flush=True,
            )

    summary = aggregate(rows)
    payload = {
        "experiment": "part_v_stage2_autogen_attribution",
        "hypothesis": "H4 adapter-only attribution transfer",
        "claim_note": (
            "Attribution only on AutoGen — no repair yet. "
            "Framework invariance Stage 2. Not SWE-bench."
        ),
        "summary": summary,
        "rows": rows,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("\n=== Stage 2 summary ===")
    print(json.dumps(summary, indent=2))
    print(f"gate={'PASS' if summary['stage2_gate_pass'] else 'FAIL'}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
