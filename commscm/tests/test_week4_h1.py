"""Week-4 Phase A / H1 tests."""

from __future__ import annotations

import unittest

from commscm.attribution.engines import DescendantReplayEstimator
from commscm.benchmarks.week3_random import build_random_trace
from commscm.ccas.operators import (
    CRGuidedOperator,
    RandomOperator,
    RewardOnlyOperator,
    gold_harmful_edges,
    unique_edges_in_order,
)
from commscm.eval.h1_edges import score_proposal
from commscm.estimators.replay import DescendantReplayEngine, fault_marker_outcome
from commscm.runtime.mechanisms import MechanismRegistry


class Week4H1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.trace = build_random_trace(7, n_events=16)
        self.report = DescendantReplayEstimator(
            DescendantReplayEngine(fault_marker_outcome, MechanismRegistry())
        ).score(self.trace)

    def test_phase_b_apply_registers_new_architecture(self) -> None:
        op = CRGuidedOperator()
        prop = op.propose(self.trace, self.report)
        new_id = op.apply(prop.base_architecture_id, prop)
        self.assertTrue(prop.meta.get("mutation"))
        self.assertNotEqual(new_id, prop.base_architecture_id)

    def test_cr_proposal_nonempty_ranked_edits(self) -> None:
        prop = CRGuidedOperator().propose(self.trace, self.report)
        self.assertGreater(len(prop.edits), 0)
        self.assertEqual(prop.edits[0].kind.value, "prune_edge")

    def test_gold_harmful_edges_incident_to_fault(self) -> None:
        gold = gold_harmful_edges(self.trace)
        self.assertTrue(gold)
        g = self.trace.gold_fault_event_id
        self.assertTrue(any(g in e for e in gold))

    def test_reward_only_ignores_delta_y_ordering_contract(self) -> None:
        # Smoke: both produce proposals; methods differ in meta.
        a = CRGuidedOperator().propose(self.trace, self.report)
        b = RewardOnlyOperator().propose(self.trace, self.report)
        self.assertEqual(a.meta["method"], "cr_guided")
        self.assertEqual(b.meta["method"], "random" if False else "reward_only")

    def test_h1_score_smoke(self) -> None:
        prop = RandomOperator(seed=1).propose(self.trace, self.report)
        gold = gold_harmful_edges(self.trace)
        s = score_proposal(prop, gold)
        self.assertIn("hit_at_1", s)
        edges = unique_edges_in_order(prop.edits)
        self.assertGreater(len(edges), 0)


if __name__ == "__main__":
    unittest.main()
