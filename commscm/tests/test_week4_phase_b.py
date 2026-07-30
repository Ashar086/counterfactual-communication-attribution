"""Week-4 Phase B: single architecture edit apply."""

from __future__ import annotations

import unittest

from commscm.attribution.engines import DescendantReplayEstimator
from commscm.benchmarks.week3_random import build_random_trace
from commscm.ccas.apply_edit import (
    ArchitectureRegistry,
    apply_edit_to_trace,
    apply_single_edit,
    rematerialize,
)
from commscm.ccas.interfaces import ArchitectureEdit, ArchitectureEditKind
from commscm.ccas.operators import CRGuidedOperator, sink_fault_outcome
from commscm.estimators.replay import DescendantReplayEngine, fault_marker_outcome
from commscm.runtime.mechanisms import MechanismRegistry


class PhaseBTests(unittest.TestCase):
    def setUp(self) -> None:
        self.trace = build_random_trace(11, n_events=16)
        self.trace = self.trace.model_copy(
            update={"dag": rematerialize(self.trace.dag)}, deep=True
        )
        self.report = DescendantReplayEstimator(
            DescendantReplayEngine(fault_marker_outcome, MechanismRegistry())
        ).score(self.trace)

    def test_prune_removes_parent_edge(self) -> None:
        # Find any edge
        tgt = None
        src = None
        for eid, ev in self.trace.dag.events.items():
            if ev.parents:
                tgt, src = eid, ev.parents[0]
                break
        self.assertIsNotNone(tgt)
        edit = ArchitectureEdit(
            kind=ArchitectureEditKind.PRUNE_EDGE,
            source_event_id=src,
            target_event_id=tgt,
        )
        new_dag = apply_single_edit(self.trace.dag, edit)
        self.assertNotIn(src, new_dag.events[tgt].parents)

    def test_weaken_marks_parent(self) -> None:
        tgt = src = None
        for eid, ev in self.trace.dag.events.items():
            if ev.parents:
                tgt, src = eid, ev.parents[0]
                break
        edit = ArchitectureEdit(
            kind=ArchitectureEditKind.WEAKEN_EDGE,
            source_event_id=src,
            target_event_id=tgt,
        )
        new_dag = apply_single_edit(self.trace.dag, edit)
        self.assertIn(src, new_dag.events[tgt].meta.get("weakened_parents", []))
        self.assertIn(src, new_dag.events[tgt].parents)

    def test_insert_verifier_rewires_edge(self) -> None:
        tgt = src = None
        for eid, ev in self.trace.dag.events.items():
            if ev.parents:
                tgt, src = eid, ev.parents[0]
                break
        edit = ArchitectureEdit(
            kind=ArchitectureEditKind.INSERT_VERIFIER,
            source_event_id=src,
            target_event_id=tgt,
        )
        new_dag = apply_single_edit(self.trace.dag, edit)
        self.assertNotIn(src, new_dag.events[tgt].parents)
        verifiers = [e for e in new_dag.events if e.startswith("V_")]
        self.assertTrue(verifiers)
        self.assertTrue(any(v in new_dag.events[tgt].parents for v in verifiers))

    def test_registry_apply_top1_only(self) -> None:
        reg = ArchitectureRegistry()
        op = CRGuidedOperator(registry=reg)
        prop = op.propose(self.trace, self.report)
        self.assertGreaterEqual(len(prop.edits), 2)
        new_id = op.apply(prop.base_architecture_id, prop)
        self.assertNotEqual(new_id, prop.base_architecture_id)
        self.assertTrue(reg.contains(new_id))
        # Exactly one edit recorded
        self.assertEqual(len(reg._meta[new_id]["edits"]), 1)

    def test_chain_cr_prune_repairs_terminal_sink(self) -> None:
        from commscm.benchmarks.week4_chain import build_chain_fault_trace

        tr = build_chain_fault_trace(n_events=8)
        self.assertEqual(sink_fault_outcome(tr.dag), 0.0)
        report = DescendantReplayEstimator(
            DescendantReplayEngine(fault_marker_outcome, MechanismRegistry())
        ).score(tr)
        prop = CRGuidedOperator().propose(tr, report)
        edit = prop.edits[0]
        self.assertEqual((edit.source_event_id, edit.target_event_id), ("E0", "E1"))
        new_tr = apply_edit_to_trace(tr, edit, outcome_fn=sink_fault_outcome)
        self.assertEqual(new_tr.outcome.reward, 1.0)


if __name__ == "__main__":
    unittest.main()
