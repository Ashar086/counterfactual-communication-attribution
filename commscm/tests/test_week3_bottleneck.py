"""Week-3 Replay Complexity Suite + COW descendant replay tests."""

from __future__ import annotations

import unittest

from commscm.attribution.engines import ExactReplayOracle
from commscm.benchmarks.replay_complexity import (
    ReplayComplexitySpec,
    build_descendant_ratio_suite,
    build_replay_complexity_trace,
)
from commscm.estimators.replay import (
    CostBreakdown,
    DescendantReplayEngine,
    FullReplayEngine,
    OverlayEventDAG,
    fault_marker_outcome,
)
from commscm.interventions.soft import SoftIntervention
from commscm.runtime.mechanisms import MechanismRegistry, descendants_of


class ReplayComplexityTests(unittest.TestCase):
    def test_descendant_ratio_approximately_respected(self) -> None:
        for ratio in (0.1, 0.4, 0.9):
            tr = build_replay_complexity_trace(
                ReplayComplexitySpec(
                    n_events=100,
                    branching_factor=2,
                    descendant_ratio=ratio,
                    shared_subgraph_frac=0.25,
                )
            )
            actual = len(descendants_of(tr.dag, "E0")) / 99
            self.assertAlmostEqual(actual, ratio, delta=0.02)

    def test_parallel_nodes_not_descendants(self) -> None:
        tr = build_replay_complexity_trace(
            ReplayComplexitySpec(
                n_events=80,
                branching_factor=3,
                descendant_ratio=0.3,
                shared_subgraph_frac=0.0,
            )
        )
        desc = descendants_of(tr.dag, "E0")
        for pid in tr.extra["parallel_ids"]:
            self.assertNotIn(pid, desc)

    def test_cost_breakdown_present(self) -> None:
        tr = build_replay_complexity_trace(
            ReplayComplexitySpec(
                n_events=40, branching_factor=2, descendant_ratio=0.5, shared_subgraph_frac=0.2
            )
        )
        eng = FullReplayEngine(
            fault_marker_outcome, MechanismRegistry(), structural_cost_iters=50
        )
        result = eng.replay(tr, SoftIntervention(event_id="E0", use_channel_null=True))
        self.assertIsInstance(result.cost, CostBreakdown)
        self.assertGreater(result.cost.structural_evals, 0)
        self.assertEqual(result.cost.materialized_nodes, len(tr.dag.events))

    def test_cow_materializes_only_affected_subgraph(self) -> None:
        tr = build_replay_complexity_trace(
            ReplayComplexitySpec(
                n_events=120, branching_factor=2, descendant_ratio=0.2, shared_subgraph_frac=0.0
            )
        )
        eng = DescendantReplayEngine(
            fault_marker_outcome, MechanismRegistry(), structural_cost_iters=20
        )
        r = eng.replay(tr, SoftIntervention(event_id="E0", use_channel_null=True))
        n_desc = len(descendants_of(tr.dag, "E0"))
        self.assertEqual(r.materialization_mode, "cow_overlay")
        self.assertIsInstance(r.counterfactual_view(), OverlayEventDAG)
        # intervention root + descendants
        self.assertEqual(r.cost.materialized_nodes, n_desc + 1)
        self.assertLess(r.cost.materialized_nodes, len(tr.dag.events))

    def test_descendant_evals_and_nodes_scale_with_ratio(self) -> None:
        traces = build_descendant_ratio_suite(
            n_events=120,
            branching_factor=2,
            ratios=[0.2, 0.8],
            shared_subgraph_frac=0.0,
        )
        eng = DescendantReplayEngine(
            fault_marker_outcome, MechanismRegistry(), structural_cost_iters=20
        )
        evals = []
        nodes = []
        for tr in traces:
            r = eng.replay(tr, SoftIntervention(event_id="E0", use_channel_null=True))
            evals.append(r.cost.structural_evals)
            nodes.append(r.cost.materialized_nodes)
        self.assertLess(evals[0], evals[1])
        self.assertLess(nodes[0], nodes[1])
        full = FullReplayEngine(fault_marker_outcome, MechanismRegistry(), structural_cost_iters=20)
        full_r = full.replay(traces[0], SoftIntervention(event_id="E0", use_channel_null=True))
        self.assertLess(evals[0], full_r.cost.structural_evals)
        self.assertLess(nodes[0], full_r.cost.materialized_nodes)

    def test_cow_matches_oracle_reward(self) -> None:
        tr = build_replay_complexity_trace(
            ReplayComplexitySpec(
                n_events=60, branching_factor=2, descendant_ratio=0.4, shared_subgraph_frac=0.25
            )
        )
        kwargs = dict(structural_cost_iters=10)
        o = FullReplayEngine(fault_marker_outcome, MechanismRegistry(), **kwargs)
        d = DescendantReplayEngine(fault_marker_outcome, MechanismRegistry(), **kwargs)
        intervention = SoftIntervention(event_id="E0", use_channel_null=True)
        self.assertEqual(
            o.replay(tr, intervention).counterfactual_reward,
            d.replay(tr, intervention).counterfactual_reward,
        )

    def test_attribution_report_aggregates_cost(self) -> None:
        tr = build_replay_complexity_trace(
            ReplayComplexitySpec(
                n_events=24, branching_factor=2, descendant_ratio=0.5, shared_subgraph_frac=0.0
            )
        )
        report = ExactReplayOracle(
            FullReplayEngine(fault_marker_outcome, MechanismRegistry(), structural_cost_iters=10)
        ).score(tr)
        self.assertIn("cost_breakdown", report.extra)
        self.assertGreater(report.extra["cost_breakdown"]["structural_evals"], 0)


if __name__ == "__main__":
    unittest.main()
