"""
Part V Stage 3 — Same-task LangGraph vs AutoGen attribution comparison.

Exact same (task, poison) pairs on both frameworks. Compare Top-1, Kendall τ,
Gold Edge Hit. No repair. Adapter-only; frozen CR.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from credit_assignment.fault_injection import FaultInjector, PoisonMode
from credit_assignment.graph import run_pipeline
from credit_assignment.tasks import load_tasks
from credit_assignment import llm as _llm  # noqa: F401
from commscm.adapters.autogen.extract import autogen_reward_outcome, autogen_state_to_run_trace
from commscm.adapters.autogen.mechanisms import make_autogen_sticky_registry
from commscm.adapters.autogen.pipeline import run_autogen_pipeline
from commscm.attribution.subset import SubsetAttributionEngine
from commscm.estimators.replay import DescendantReplayEngine
from commscm.metrics.ranking_stability import kendall_tau
from commscm.traces.langgraph_extract import agent_state_to_run_trace, langgraph_reward_outcome
from commscm.traces.langgraph_mechanisms import make_langgraph_sticky_registry

AGENT_EVENTS = {"C1", "C2", "C3", "C4", "C5"}
MODES = (PoisonMode.POISON_PLANNER, PoisonMode.POISON_CODER, PoisonMode.POISON_REVIEWER)


def _score_langgraph(tr):
    mechs = make_langgraph_sticky_registry(tr.dag)
    return SubsetAttributionEngine(
        DescendantReplayEngine(langgraph_reward_outcome, mechs, structural_cost_iters=0),
        AGENT_EVENTS,
        name="LangGraphCR",
    ).score(tr)


def _score_autogen(tr):
    mechs = make_autogen_sticky_registry(tr.dag)
    return SubsetAttributionEngine(
        DescendantReplayEngine(autogen_reward_outcome, mechs, structural_cost_iters=0),
        AGENT_EVENTS,
        name="AutoGenCR",
    ).score(tr)


def _ranking(report) -> list[str]:
    return [r.event_id for r in sorted(report.rows, key=lambda x: (-x.delta_y, x.event_id))]


def run_pair(*, task, mode: PoisonMode, pair_idx: int) -> dict:
    row: dict = {
        "pair_idx": pair_idx,
        "task_id": task.task_id,
        "poison_mode": mode.value,
        "gold": None,
    }
    # LangGraph
    lg_state = run_pipeline(
        task.prompt,
        fault_injector=FaultInjector(mode=mode),
        entry_point=task.entry_point,
        test_cases=list(task.test_cases),
        reference_solution=task.reference_solution,
    )
    lg_tr = agent_state_to_run_trace(
        lg_state, run_id=f"lg_{pair_idx}_{mode.value}_{task.task_id}", task_id=task.task_id
    )
    lg_rep = _score_langgraph(lg_tr)
    lg_rank = _ranking(lg_rep)

    # AutoGen
    ag_state = run_autogen_pipeline(
        task.prompt,
        fault_injector=FaultInjector(mode=mode),
        entry_point=task.entry_point,
        test_cases=list(task.test_cases),
        reference_solution=task.reference_solution,
    )
    ag_tr = autogen_state_to_run_trace(
        ag_state, run_id=f"ag_{pair_idx}_{mode.value}_{task.task_id}", task_id=task.task_id
    )
    ag_rep = _score_autogen(ag_tr)
    ag_rank = _ranking(ag_rep)

    gold = lg_tr.gold_fault_event_id
    row.update(
        {
            "gold": gold,
            "langgraph": {
                "y": float(lg_state.global_reward),
                "cr_top1": lg_rep.predicted_top1,
                "cr_ranking": lg_rank,
                "cr_hit": lg_rep.predicted_top1 == gold,
            },
            "autogen": {
                "y": float(ag_state.global_reward),
                "cr_top1": ag_rep.predicted_top1,
                "cr_ranking": ag_rank,
                "cr_hit": ag_rep.predicted_top1 == gold,
            },
            "top1_agree": lg_rep.predicted_top1 == ag_rep.predicted_top1,
            "kendall_tau": kendall_tau(lg_rank, ag_rank),
            "both_gold_hit": (
                lg_rep.predicted_top1 == gold and ag_rep.predicted_top1 == gold
            ),
        }
    )
    return row


def aggregate(rows: list[dict]) -> dict:
    n = len(rows)
    return {
        "n_pairs": n,
        "top1_agreement": sum(1 for r in rows if r.get("top1_agree")) / n if n else 0.0,
        "mean_kendall_tau": (
            sum(float(r["kendall_tau"]) for r in rows) / n if n else None
        ),
        "langgraph_gold_hit": (
            sum(1 for r in rows if r.get("langgraph", {}).get("cr_hit")) / n if n else 0.0
        ),
        "autogen_gold_hit": (
            sum(1 for r in rows if r.get("autogen", {}).get("cr_hit")) / n if n else 0.0
        ),
        "both_gold_hit": sum(1 for r in rows if r.get("both_gold_hit")) / n if n else 0.0,
        "stage3_gate_pass": (
            n > 0
            and all(r.get("top1_agree") for r in rows)
            and all(r.get("both_gold_hit") for r in rows)
        ),
        "core_unchanged": True,
    }


def build_pairs(n_pairs: int, tasks: list) -> list:
    pairs = []
    i = 0
    while len(pairs) < n_pairs:
        task = tasks[i % len(tasks)]
        mode = MODES[i % len(MODES)]
        pairs.append((task, mode, len(pairs)))
        i += 1
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-pairs", type=int, default=15)
    parser.add_argument("--out", type=str, default="results/part_v_stage3_framework_compare.json")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY required")
    os.environ["USE_MOCK_LLM"] = "0"
    os.environ["FAIL_ON_LLM_ERROR"] = "1"

    tasks = load_tasks()
    pairs = build_pairs(args.n_pairs, tasks)
    rows: list[dict] = []
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Part V Stage 3: same-task LangGraph vs AutoGen (n_pairs={args.n_pairs})")
    for task, mode, idx in pairs:
        print(f"[{idx+1}/{args.n_pairs}] {mode.value} {task.task_id} ...", flush=True)
        row = run_pair(task=task, mode=mode, pair_idx=idx)
        rows.append(row)
        print(
            f"  LG={row['langgraph']['cr_top1']} AG={row['autogen']['cr_top1']} "
            f"agree={row['top1_agree']} tau={row['kendall_tau']:.3f}",
            flush=True,
        )
        summary = aggregate(rows)
        out_path.write_text(
            json.dumps(
                {
                    "experiment": "part_v_stage3_framework_compare",
                    "partial": idx + 1 < args.n_pairs,
                    "summary": summary,
                    "rows": rows,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    summary = aggregate(rows)
    payload = {
        "experiment": "part_v_stage3_framework_compare",
        "hypothesis": "Same communication structure → same CR attribution across frameworks",
        "summary": summary,
        "rows": rows,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("\n=== Stage 3 summary ===")
    print(json.dumps(summary, indent=2))
    print(f"gate={'PASS' if summary['stage3_gate_pass'] else 'FAIL'}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
