"""Week-2 stress tests: cascade root cause + noise robustness."""

from __future__ import annotations

import unittest

from commscm.attribution.exact import attribute_exact
from commscm.benchmarks.causal_comm_bench import build_gold_fault_dataset
from commscm.benchmarks.stress import (
    build_cascade_engine,
    build_fault_cascade_dataset,
    noise_perturbed_case,
)
from commscm.eval.localization import aggregate_localization
from commscm.experiments.week2_localize import build_engine


class CascadeTests(unittest.TestCase):
    def test_root_cause_ranks_first(self) -> None:
        engine = build_cascade_engine()
        case = build_fault_cascade_dataset()[0]
        report = attribute_exact(case.trace, engine)
        self.assertEqual(report.predicted_top1, "C2")
        self.assertTrue(report.hit_at_1)
        # Cascaded memory symptom should not outrank the root under binary primary FAULT_
        c3 = next(r for r in report.rows if r.event_id == "C3")
        c2 = next(r for r in report.rows if r.event_id == "C2")
        self.assertGreaterEqual(c2.delta_y, c3.delta_y)


class NoiseTests(unittest.TestCase):
    def test_noise_does_not_collapse_localization(self) -> None:
        engine = build_engine()
        reports = []
        for case in build_gold_fault_dataset():
            noisy = noise_perturbed_case(case, rate=0.3, seed=42)
            reports.append(attribute_exact(noisy.trace, engine))
        metrics = aggregate_localization(reports)
        # Exact oracle on marker faults should remain perfect if noise avoids FAULT_
        self.assertEqual(metrics.precision_at_1, 1.0)
        self.assertEqual(metrics.mrr, 1.0)


if __name__ == "__main__":
    unittest.main()
