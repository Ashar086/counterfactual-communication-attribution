"""Week-4 Phase D iterative CCAS tests."""

from __future__ import annotations

import unittest

from commscm.benchmarks.week4_multipath import build_multipath_fault_trace
from commscm.ccas.loop import CCASLoop, make_operator
from commscm.ccas.operators import sink_fault_outcome


class PhaseDTests(unittest.TestCase):
    def test_multipath_needs_two_edits(self) -> None:
        tr = build_multipath_fault_trace(branch_len=2, seed=0)
        self.assertEqual(sink_fault_outcome(tr.dag), 0.0)
        self.assertEqual(tr.extra["min_edits_to_repair"], 2)

    def test_cr_repairs_within_budget_2(self) -> None:
        tr = build_multipath_fault_trace(branch_len=2, seed=1)
        result = CCASLoop(make_operator("cr_guided"), edit_budget=2).run(tr)
        self.assertTrue(result.success)
        self.assertEqual(result.n_edits, 2)
        self.assertGreaterEqual(result.gold_edges_hit, 1)

    def test_budget_1_cannot_finish(self) -> None:
        tr = build_multipath_fault_trace(branch_len=2, seed=2)
        result = CCASLoop(make_operator("cr_guided"), edit_budget=1).run(tr)
        self.assertFalse(result.success)
        self.assertEqual(result.n_edits, 1)

    def test_reward_only_runs(self) -> None:
        tr = build_multipath_fault_trace(branch_len=2, seed=3)
        result = CCASLoop(make_operator("reward_only"), edit_budget=4).run(tr)
        self.assertGreaterEqual(result.n_edits, 1)


if __name__ == "__main__":
    unittest.main()
