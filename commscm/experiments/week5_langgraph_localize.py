"""
Week 5: LangGraph traces → attribution only (no CCAS edits).

Default: offline poisoned AgentStates (no API).
Optional: --live runs credit_assignment.graph with OpenAI.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from credit_assignment.fault_injection import FaultInjector, PoisonMode
from commscm.attribution.report import AttributionReport
from commscm.attribution.subset import SubsetAttributionEngine
from commscm.benchmarks.week5_langgraph_offline import build_offline_langgraph_dataset
from commscm.estimators.replay import DescendantReplayEngine
from commscm.traces.langgraph_extract import agent_state_to_run_trace, langgraph_reward_outcome
from commscm.traces.langgraph_mechanisms import make_langgraph_sticky_registry

AGENT_EVENTS = {"C1", "C2", "C3", "C4", "C5"}


def _reward_only_top1(report: AttributionReport) -> str | None:
    if not report.rows:
        return None
    if report.factual_reward >= 1.0:
        return report.rows[-1].event_id
    order = sorted(report.rows, key=lambda r: r.event_id, reverse=True)
    return order[0].event_id


def _random_top1(report: AttributionReport, seed: int) -> str | None:
    import random

    ids = [r.event_id for r in report.rows]
    if not ids:
        return None
    return random.Random(seed).choice(ids)


def _score_trace(tr):
    mechs = make_langgraph_sticky_registry(tr.dag)
    engine = SubsetAttributionEngine(
        DescendantReplayEngine(langgraph_reward_outcome, mechs, structural_cost_iters=0),
        AGENT_EVENTS,
        name="LangGraphCR",
    )
    return engine.score(tr)


def collect_live_traces(n_per_mode: int = 1) -> list:
    from credit_assignment.graph import run_pipeline
    from credit_assignment.tasks import load_tasks

    tasks = load_tasks()
    task = tasks[0]
    states = []
    for mode in (PoisonMode.POISON_PLANNER, PoisonMode.POISON_CODER, PoisonMode.POISON_REVIEWER):
        for _ in range(n_per_mode):
            states.append(
                run_pipeline(
                    task.description,
                    fault_injector=FaultInjector(mode=mode),
                    entry_point=task.entry_point,
                    test_cases=list(task.test_cases),
                    reference_solution=task.reference_solution,
                )
            )
    return states


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Run real LangGraph+LLM traces")
    parser.add_argument("--n-per-mode", type=int, default=1)
    args = parser.parse_args()

    if args.live:
        if not os.getenv("OPENAI_API_KEY"):
            raise SystemExit("--live requires OPENAI_API_KEY in environment")
        states = collect_live_traces(n_per_mode=args.n_per_mode)
        source = "live_langgraph"
    else:
        states = build_offline_langgraph_dataset()
        source = "offline_langgraph"

    rows = []
    for i, st in enumerate(states):
        tr = agent_state_to_run_trace(st, run_id=f"{source}_{i}_{st.poison_mode}")
        report = _score_trace(tr)
        cr_top = report.predicted_top1
        rw_top = _reward_only_top1(report)
        rd_top = _random_top1(report, seed=i)
        gold = tr.gold_fault_event_id
        rows.append(
            {
                "run_id": tr.run_id,
                "poison_mode": st.poison_mode,
                "gold": gold,
                "cr_top1": cr_top,
                "reward_only_top1": rw_top,
                "random_top1": rd_top,
                "cr_hit": cr_top == gold,
                "reward_only_hit": rw_top == gold,
                "random_hit": rd_top == gold,
            }
        )

    n = len(rows)
    summary = {
        "source": source,
        "n": n,
        "cr_p_at_1": sum(1 for r in rows if r["cr_hit"]) / n if n else 0.0,
        "reward_only_p_at_1": sum(1 for r in rows if r["reward_only_hit"]) / n if n else 0.0,
        "random_p_at_1": sum(1 for r in rows if r["random_hit"]) / n if n else 0.0,
        "note": (
            "Attribution only on agent events C1-C5; sticky mechanisms preserve "
            "channel-native injections. No CCAS edits. Not full H2."
        ),
    }
    summary["week5_gate_pass"] = (
        summary["cr_p_at_1"] > summary["reward_only_p_at_1"]
        and summary["cr_p_at_1"] > summary["random_p_at_1"]
    )

    print("Week 5 — LangGraph attribution only (no CCAS edits)")
    print(f"source={source} n={n}")
    print(
        f"CR P@1={summary['cr_p_at_1']:.3f}  "
        f"reward-only={summary['reward_only_p_at_1']:.3f}  "
        f"random={summary['random_p_at_1']:.3f}"
    )
    print("Week 5 gate:", "PASS" if summary["week5_gate_pass"] else "FAIL")
    for r in rows:
        print(
            f"  {r['poison_mode']:<18} gold={r['gold']}  "
            f"CR={r['cr_top1']}  RW={r['reward_only_top1']}  RD={r['random_top1']}"
        )

    out = {"experiment": "week5_langgraph_localize", "summary": summary, "rows": rows}
    path = Path("results/week5_langgraph_localize.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
