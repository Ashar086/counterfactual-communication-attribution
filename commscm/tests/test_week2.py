"""Week-2 tests: exact replay, descendant-only recompute, localization P@1."""

from __future__ import annotations

import unittest

from commscm.attribution.exact import attribute_exact
from commscm.benchmarks.causal_comm_bench import build_gold_fault_dataset
from commscm.estimators.exact_replay import ExactReplayEngine, fault_marker_outcome
from commscm.eval.localization import aggregate_localization
from commscm.experiments.week2_localize import build_engine
from commscm.interventions.soft import SoftIntervention
from commscm.runtime.mechanisms import descendants_of
from commscm.schema.events import Channel, CommunicationEvent, EventDAG


class ReplayInvariantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = build_engine()
        self.case = build_gold_fault_dataset()[0]  # text fault on C1
        self.trace = self.case.trace

    def test_intervention_changes_only_message_content_at_target(self) -> None:
        before = self.trace.dag.events["C1"]
        result = self.engine.replay(
            self.trace, SoftIntervention(event_id="C1", use_channel_null=True)
        )
        after = result.counterfactual_dag.events["C1"]
        self.assertEqual(after.event_id, before.event_id)
        self.assertEqual(after.sender, before.sender)
        self.assertEqual(after.receiver, before.receiver)
        self.assertEqual(after.channel, before.channel)
        self.assertEqual(after.time_index, before.time_index)
        self.assertEqual(after.parents, before.parents)
        self.assertNotEqual(after.message, before.message)
        self.assertIn("NULL_TEXT", after.message)

    def test_event_ids_unchanged(self) -> None:
        result = self.engine.replay(
            self.trace, SoftIntervention(event_id="C2", use_channel_null=True)
        )
        self.assertEqual(
            set(result.counterfactual_dag.events), set(self.trace.dag.events)
        )

    def test_replay_deterministic(self) -> None:
        inter = SoftIntervention(event_id="C1", use_channel_null=True)
        a = self.engine.replay(self.trace, inter)
        b = self.engine.replay(self.trace, inter)
        self.assertEqual(a.counterfactual_reward, b.counterfactual_reward)
        for eid in self.trace.dag.events:
            self.assertEqual(
                a.counterfactual_dag.events[eid].message,
                b.counterfactual_dag.events[eid].message,
            )

    def test_only_descendants_recomputed(self) -> None:
        result = self.engine.replay(
            self.trace, SoftIntervention(event_id="C1", use_channel_null=True)
        )
        # C1 intervened; C5–C7 have mechanisms and are descendants of C1 via C5.
        self.assertEqual(set(result.recomputed_event_ids), {"C1", "C5", "C6", "C7"})
        for eid in ("C0", "C2", "C3", "C4"):
            self.assertIn(eid, result.unchanged_event_ids)

    def test_non_descendants_bitwise_identical(self) -> None:
        result = self.engine.replay(
            self.trace, SoftIntervention(event_id="C1", use_channel_null=True)
        )
        for eid in result.unchanged_event_ids:
            self.assertEqual(
                result.counterfactual_dag.events[eid].message,
                self.trace.dag.events[eid].message,
            )


class LocalizationTests(unittest.TestCase):
    def test_gold_fault_ranks_first_on_all_synth_traces(self) -> None:
        engine = build_engine()
        reports = []
        for case in build_gold_fault_dataset():
            report = attribute_exact(case.trace, engine)
            reports.append(report)
            self.assertTrue(
                report.hit_at_1,
                msg=(
                    f"{case.case_id}: expected {case.true_event_id} "
                    f"got {report.predicted_top1} ranking="
                    f"{[(r.event_id, r.delta_y) for r in report.rows]}"
                ),
            )
        metrics = aggregate_localization(reports)
        self.assertEqual(metrics.precision_at_1, 1.0)
        self.assertEqual(metrics.mrr, 1.0)

    def test_cr_sign_convention(self) -> None:
        engine = build_engine()
        case = build_gold_fault_dataset()[0]
        report = attribute_exact(case.trace, engine)
        gold_row = next(r for r in report.rows if r.event_id == case.true_event_id)
        # Nulling the fault should improve Y ⇒ ΔY > 0 and CR = Yf - Ycf < 0
        self.assertGreater(gold_row.delta_y, 0.0)
        self.assertLess(gold_row.cr, 0.0)
        self.assertEqual(gold_row.rank, 1)


class OutcomeFnTests(unittest.TestCase):
    def test_fault_marker_outcome(self) -> None:
        dag = EventDAG()
        dag.add(
            CommunicationEvent(
                event_id="a",
                sender="s",
                receiver="r",
                channel=Channel.TEXT,
                message="ok",
                time_index=0,
            )
        )
        self.assertEqual(fault_marker_outcome(dag), 1.0)
        dag2 = EventDAG()
        dag2.add(
            CommunicationEvent(
                event_id="a",
                sender="s",
                receiver="r",
                channel=Channel.TEXT,
                message="FAULT_X",
                time_index=0,
            )
        )
        self.assertEqual(fault_marker_outcome(dag2), 0.0)


if __name__ == "__main__":
    unittest.main()
