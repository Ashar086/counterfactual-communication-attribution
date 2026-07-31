"""Unit tests for Week 6 live edit adapter + failure taxonomy."""

from __future__ import annotations

import unittest

from commscm.ccas.interfaces import ArchitectureEdit, ArchitectureEditKind
from commscm.experiments.week6_live_repair import classify_failure
from commscm.traces.langgraph_live_edit import (
    edit_to_intervention,
    first_prune_or_weaken,
    gated_parent_text,
    intervention_supported,
)


class TestLiveEditAdapter(unittest.TestCase):
    def test_first_skips_verifier(self):
        edits = [
            ArchitectureEdit(
                kind=ArchitectureEditKind.INSERT_VERIFIER,
                source_event_id="C3",
                target_event_id="C4",
            ),
            ArchitectureEdit(
                kind=ArchitectureEditKind.PRUNE_EDGE,
                source_event_id="C3",
                target_event_id="C4",
            ),
        ]
        e = first_prune_or_weaken(edits)
        self.assertIsNotNone(e)
        self.assertEqual(e.kind, ArchitectureEditKind.PRUNE_EDGE)

    def test_prefers_agent_edge_over_c0(self):
        edits = [
            ArchitectureEdit(
                kind=ArchitectureEditKind.PRUNE_EDGE,
                source_event_id="C0",
                target_event_id="C1",
            ),
            ArchitectureEdit(
                kind=ArchitectureEditKind.PRUNE_EDGE,
                source_event_id="C1",
                target_event_id="C2",
            ),
        ]
        e = first_prune_or_weaken(edits)
        self.assertEqual((e.source_event_id, e.target_event_id), ("C1", "C2"))

    def test_prefers_outgoing_from_top1_toward_sink(self):
        edits = [
            ArchitectureEdit(
                kind=ArchitectureEditKind.PRUNE_EDGE,
                source_event_id="C1",
                target_event_id="C2",
            ),
            ArchitectureEdit(
                kind=ArchitectureEditKind.PRUNE_EDGE,
                source_event_id="C2",
                target_event_id="C3",
            ),
            ArchitectureEdit(
                kind=ArchitectureEditKind.PRUNE_EDGE,
                source_event_id="C2",
                target_event_id="C4",
            ),
        ]
        e = first_prune_or_weaken(
            edits,
            top1_event="C2",
            target_time_index={"C2": 2, "C3": 3, "C4": 4},
        )
        self.assertEqual((e.source_event_id, e.target_event_id), ("C2", "C4"))

    def test_c3_c4_supported(self):
        e = ArchitectureEdit(
            kind=ArchitectureEditKind.PRUNE_EDGE,
            source_event_id="C3",
            target_event_id="C4",
        )
        self.assertTrue(intervention_supported(e))
        iv = edit_to_intervention(e)
        self.assertEqual(iv["kind"], "prune_edge")

    def test_gated_weaken(self):
        ivs = [{"source_event_id": "C1", "target_event_id": "C2", "kind": "weaken_edge"}]
        text, mode = gated_parent_text(
            interventions=ivs,
            src="C1",
            tgt="C2",
            factual="POISONED PLAN",
            prune_fallback="task",
        )
        self.assertEqual(mode, "weaken_edge")
        self.assertNotEqual(text, "POISONED PLAN")


class TestFailureTaxonomy(unittest.TestCase):
    def test_success_none(self):
        self.assertIsNone(
            classify_failure(
                attribution_ok=True,
                extract_ok=True,
                pipeline_ok=True,
                repair_ok=True,
                attribution_correct=True,
                hit_gold_edge=True,
                y_before=0.0,
                y_after=1.0,
                sink_valid=True,
                edit_supported=True,
                n_edits=1,
            )
        )

    def test_f1(self):
        self.assertEqual(
            classify_failure(
                attribution_ok=True,
                extract_ok=True,
                pipeline_ok=True,
                repair_ok=True,
                attribution_correct=False,
                hit_gold_edge=False,
                y_before=0.0,
                y_after=0.0,
                sink_valid=True,
                edit_supported=True,
                n_edits=1,
            ),
            "F1",
        )

    def test_f3(self):
        self.assertEqual(
            classify_failure(
                attribution_ok=True,
                extract_ok=True,
                pipeline_ok=True,
                repair_ok=True,
                attribution_correct=True,
                hit_gold_edge=True,
                y_before=0.0,
                y_after=0.5,
                sink_valid=True,
                edit_supported=True,
                n_edits=1,
            ),
            "F3",
        )

    def test_f5(self):
        self.assertEqual(
            classify_failure(
                attribution_ok=False,
                extract_ok=True,
                pipeline_ok=True,
                repair_ok=False,
                attribution_correct=False,
                hit_gold_edge=False,
                y_before=0.0,
                y_after=None,
                sink_valid=False,
                edit_supported=False,
                n_edits=0,
            ),
            "F5",
        )


if __name__ == "__main__":
    unittest.main()
