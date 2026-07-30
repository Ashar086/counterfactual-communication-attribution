#!/usr/bin/env python3
"""
Week 2 experiment: Can exact CF communication attribution localize the fault?

Produces the localization table and aggregate P@1 / Recall@k / MRR.
"""

from __future__ import annotations

import json
from pathlib import Path

from commscm.attribution.exact import attribute_exact
from commscm.benchmarks.causal_comm_bench import build_gold_fault_dataset
from commscm.estimators.exact_replay import ExactReplayEngine, fault_marker_outcome
from commscm.eval.localization import aggregate_localization
from commscm.runtime.mechanisms import MechanismRegistry, default_passthrough_mechanism


def _coder_mechanism(event, parent_msgs: dict[str, str]) -> str:
    return (
        f"CODE from plan={parent_msgs['C1']} tool={parent_msgs['C2']} "
        f"mem={parent_msgs['C3']} ret={parent_msgs['C4']}"
    )


def _review_mechanism(event, parent_msgs: dict[str, str]) -> str:
    return f"REVIEW of {parent_msgs['C5']}"


def _exec_mechanism(event, parent_msgs: dict[str, str]) -> str:
    return f'{{"exec":"{parent_msgs["C6"]}"}}'


def build_engine() -> ExactReplayEngine:
    registry = MechanismRegistry(
        {
            "C5": _coder_mechanism,
            "C6": _review_mechanism,
            "C7": _exec_mechanism,
            # leave C1–C4 exogenous except when intervened
        }
    )
    # unused default still imported for clarity
    _ = default_passthrough_mechanism
    return ExactReplayEngine(outcome_fn=fault_marker_outcome, mechanisms=registry)


def main() -> None:
    engine = build_engine()
    cases = build_gold_fault_dataset()
    reports = []
    print("Trace           Fault Type                 True   Pred   P@1  Replay(ms)")
    print("-" * 78)
    for case in cases:
        report = attribute_exact(case.trace, engine)
        reports.append(report)
        mark = "Y" if report.hit_at_1 else "N"
        top_row = report.rows[0]
        print(
            f"{case.case_id:<15} {case.fault_type:<25} "
            f"{case.true_event_id:<6} {report.predicted_top1:<6} "
            f"{mark:<4} {report.total_runtime_ms:>8.1f}"
        )
        # compact CR table
        print("  Rank Event Ch        CR      dY  #recomp")
        for row in report.rows[:5]:
            print(
                f"  {row.rank:>4} {row.event_id:<5} {row.channel:<9} "
                f"{row.cr:>6.2f} {row.delta_y:>6.2f} {row.recomputed_count:>7}"
            )

    metrics = aggregate_localization(reports)
    print("\n=== Aggregate ===")
    print(json.dumps(metrics.model_dump(), indent=2))

    out = Path("results/week2_localization.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metrics": metrics.model_dump(),
        "cases": [
            {
                "trace": c.case_id,
                "fault_type": c.fault_type,
                "true_event": c.true_event_id,
                "predicted_top1": r.predicted_top1,
                "p_at_1": bool(r.hit_at_1),
                "total_runtime_ms": r.total_runtime_ms,
                "ranking": [row.model_dump() for row in r.rows],
            }
            for c, r in zip(cases, reports)
        ],
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
