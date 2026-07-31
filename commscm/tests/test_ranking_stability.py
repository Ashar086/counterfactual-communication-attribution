"""Unit tests for attribution ranking stability metrics."""

from __future__ import annotations

import unittest

from commscm.metrics.ranking_stability import (
    kendall_tau,
    mean_pairwise_kendall,
    summarize_stability_group,
    top1_modal_agreement,
    top1_pairwise_agreement,
)


class TestKendallTau(unittest.TestCase):
    def test_identical(self):
        r = ["C1", "C2", "C3"]
        self.assertAlmostEqual(kendall_tau(r, r), 1.0)

    def test_reverse(self):
        a = ["C1", "C2", "C3"]
        b = ["C3", "C2", "C1"]
        self.assertAlmostEqual(kendall_tau(a, b), -1.0)

    def test_one_swap(self):
        a = ["C1", "C2", "C3"]
        b = ["C2", "C1", "C3"]
        # one discordant pair out of three → (2-1)/3 = 1/3
        self.assertAlmostEqual(kendall_tau(a, b), 1.0 / 3.0)


class TestTop1(unittest.TestCase):
    def test_modal_full_agree(self):
        m = top1_modal_agreement(["C1", "C1", "C1", "C1", "C1"])
        self.assertEqual(m["modal_top1"], "C1")
        self.assertAlmostEqual(m["agreement"], 1.0)

    def test_pairwise(self):
        self.assertAlmostEqual(top1_pairwise_agreement(["C1", "C1", "C2"]), 1.0 / 3.0)


class TestSummarize(unittest.TestCase):
    def test_group(self):
        rows = [
            {"attribution_ok": True, "cr_top1": "C1", "cr_ranking": ["C1", "C2", "C3"]},
            {"attribution_ok": True, "cr_top1": "C1", "cr_ranking": ["C1", "C3", "C2"]},
            {"attribution_ok": True, "cr_top1": "C1", "cr_ranking": ["C1", "C2", "C3"]},
        ]
        s = summarize_stability_group(task_id="t", poison_mode="POISON_PLANNER", rows=rows)
        self.assertEqual(s["modal_top1"], "C1")
        self.assertAlmostEqual(s["top1_agreement_vs_mode"], 1.0)
        self.assertIsNotNone(s["mean_pairwise_kendall_tau"])
        self.assertGreaterEqual(s["mean_pairwise_kendall_tau"], 0.0)


class TestMeanPairwise(unittest.TestCase):
    def test_empty(self):
        self.assertIsNone(mean_pairwise_kendall([]))


if __name__ == "__main__":
    unittest.main()
