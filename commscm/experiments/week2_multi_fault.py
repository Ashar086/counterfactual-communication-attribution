#!/usr/bin/env python3
"""
Week-2 closer: multi-fault localization with exact replay (graded Y).

Metrics: Recall@2, nDCG@2, Kendall τ, Spearman vs binary relevance.
"""

from __future__ import annotations

import json
from pathlib import Path

from commscm.attribution.exact import attribute_exact
from commscm.benchmarks.causal_comm_bench import (
    build_multi_fault_dataset,
    graded_fault_outcome,
)
from commscm.estimators.exact_replay import ExactReplayEngine
from commscm.eval.localization import aggregate_multi_fault
from commscm.experiments.week2_localize import build_engine
from commscm.runtime.mechanisms import MechanismRegistry


def build_graded_engine() -> ExactReplayEngine:
    """Same mechanized descendants as Week-2, graded multi-fault outcome."""
    base = build_engine()
    return ExactReplayEngine(
        outcome_fn=graded_fault_outcome,
        mechanisms=base.mechanisms,
        nulls=base.nulls,
    )


def main() -> None:
    engine = build_graded_engine()
    cases = build_multi_fault_dataset()
    reports = []
    golds = []

    print("Trace              Faults        Top-2           R@2  nDCG@2")
    print("-" * 72)
    for case in cases:
        report = attribute_exact(case.trace, engine)
        report.extra["gold_fault_event_ids"] = list(case.true_event_ids)
        reports.append(report)
        gold = set(case.true_event_ids)
        golds.append(gold)
        top2 = [r.event_id for r in report.rows[:2]]
        hit = set(top2) & gold
        r2 = len(hit) / len(gold)
        from commscm.eval.localization import ndcg_at_k

        nd = ndcg_at_k([r.event_id for r in report.rows], gold, 2)
        print(
            f"{case.case_id:<18} {','.join(case.true_event_ids):<12} "
            f"{top2}  {r2:<4.2f} {nd:<6.3f}"
        )
        print("  Rank Event   dY")
        for row in report.rows[:4]:
            mark = "*" if row.event_id in gold else " "
            print(f"  {row.rank:>4} {row.event_id:<5}{mark} {row.delta_y:>5.2f}")

    metrics = aggregate_multi_fault(reports, golds)
    print("\n=== Multi-fault aggregate ===")
    print(json.dumps(metrics.model_dump(), indent=2))

    out = Path("results/week2_multi_fault.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "metrics": metrics.model_dump(),
                "cases": [
                    {
                        "trace": c.case_id,
                        "true_events": c.true_event_ids,
                        "ranking": [r.model_dump() for r in rep.rows],
                    }
                    for c, rep in zip(cases, reports)
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
