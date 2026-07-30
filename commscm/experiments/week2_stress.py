#!/usr/bin/env python3
"""
Week-2 closer: fault-cascade root-cause localization + semantic noise robustness.

Not a generality claim — stress tests for the exact-replay oracle.
"""

from __future__ import annotations

import json
from pathlib import Path

from commscm.attribution.exact import attribute_exact
from commscm.benchmarks.causal_comm_bench import build_gold_fault_dataset
from commscm.benchmarks.stress import (
    build_cascade_engine,
    build_fault_cascade_dataset,
    noise_perturbed_case,
)
from commscm.eval.localization import aggregate_localization
from commscm.experiments.week2_localize import build_engine


def run_cascade() -> dict:
    engine = build_cascade_engine()
    cases = build_fault_cascade_dataset()
    reports = []
    print("=== Fault cascade (gold = root cause only) ===")
    for case in cases:
        report = attribute_exact(case.trace, engine)
        reports.append(report)
        print(
            f"{case.case_id}: true={case.true_event_id} "
            f"pred={report.predicted_top1} hit={report.hit_at_1}"
        )
        print("  Rank Event   dY   note")
        symptoms = set(case.trace.extra.get("cascade_symptoms", []))
        for row in report.rows[:5]:
            tag = "ROOT" if row.event_id == case.true_event_id else (
                "symptom" if row.event_id in symptoms else ""
            )
            print(f"  {row.rank:>4} {row.event_id:<5} {row.delta_y:>5.2f}  {tag}")
    metrics = aggregate_localization(reports)
    return {"metrics": metrics.model_dump(), "n": len(cases), "hit_at_1": reports[0].hit_at_1}


def run_noise() -> dict:
    engine = build_engine()
    base_cases = build_gold_fault_dataset()
    rates = (0.0, 0.05, 0.10, 0.20, 0.30)
    seeds = (0, 1, 2)
    print("\n=== Semantic noise robustness ===")
    print("rate   P@1    MRR    mean_replay_ms")
    by_rate = {}
    for rate in rates:
        reports = []
        for seed in seeds:
            for i, case in enumerate(base_cases):
                noisy = noise_perturbed_case(case, rate=rate, seed=seed * 10 + i)
                reports.append(attribute_exact(noisy.trace, engine))
        metrics = aggregate_localization(reports)
        by_rate[str(rate)] = metrics.model_dump()
        print(
            f"{rate:<6} {metrics.precision_at_1:<6.3f} {metrics.mrr:<6.3f} "
            f"{metrics.mean_replay_ms:<.3f}"
        )
    return by_rate


def main() -> None:
    cascade = run_cascade()
    noise = run_noise()
    out = Path("results/week2_stress.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"cascade": cascade, "noise": noise}
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
