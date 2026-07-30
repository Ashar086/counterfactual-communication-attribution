"""Frozen interface contract tests — Part III must not reshape these."""

from __future__ import annotations

import unittest
from commscm.attribution.report import AttributionReport, CRRankRow
from commscm.ccas.interfaces import (
    ArchitectureEdit,
    ArchitectureEditKind,
    ArchitectureProposal,
)
from commscm.schema.events import Channel, CommunicationEvent, EventDAG, RunOutcome, RunTrace


def _tiny_trace() -> RunTrace:
    dag = EventDAG()
    dag.add(
        CommunicationEvent(
            event_id="E0",
            sender="a",
            receiver="b",
            channel=Channel.TEXT,
            message="hello",
            time_index=0,
        )
    )
    return RunTrace(
        run_id="iface_test",
        task_id="iface",
        dag=dag,
        outcome=RunOutcome(reward=1.0, success=True),
    )


class FrozenInterfaceTests(unittest.TestCase):
    def test_attribution_report_required_fields(self) -> None:
        report = AttributionReport(
            run_id="r",
            engine_name="ExactReplayOracle",
            factual_reward=1.0,
            rows=[
                CRRankRow(
                    rank=1,
                    event_id="E0",
                    channel="text",
                    cr=0.0,
                    delta_y=0.0,
                    factual_reward=1.0,
                    counterfactual_reward=1.0,
                    recomputed_count=0,
                    runtime_ms=0.0,
                )
            ],
            total_runtime_ms=0.0,
        )
        self.assertEqual(report.predicted_top1, None)
        dumped = report.model_dump()
        for key in ("run_id", "engine_name", "factual_reward", "rows", "total_runtime_ms"):
            self.assertIn(key, dumped)

    def test_architecture_proposal_closed_edit_kinds(self) -> None:
        kinds = {k.value for k in ArchitectureEditKind}
        self.assertEqual(
            kinds,
            {"prune_edge", "weaken_edge", "insert_verifier", "reroute_channel", "no_op"},
        )

    def test_architecture_proposal_forbids_extra_fields(self) -> None:
        with self.assertRaises(Exception):
            ArchitectureProposal(
                proposal_id="p1",
                base_architecture_id="arch0",
                replay_cost_ms=12.0,  # type: ignore[call-arg]
            )

    def test_proposal_required_fields(self) -> None:
        hints = ArchitectureProposal.model_fields
        self.assertIn("edits", hints)
        self.assertIn("motivating_event_ids", hints)
        self.assertIn("base_architecture_id", hints)

    def test_ccas_consumes_report_not_engine(self) -> None:
        """Proposal rationale cites event ids from the report, not engine objects."""
        trace = _tiny_trace()
        report = AttributionReport(
            run_id=trace.run_id,
            engine_name="stub",
            factual_reward=0.0,
            rows=[],
            total_runtime_ms=0.0,
            predicted_top1="E0",
        )
        proposal = ArchitectureProposal(
            proposal_id="p0",
            base_architecture_id=trace.architecture_id,
            edits=[
                ArchitectureEdit(
                    kind=ArchitectureEditKind.PRUNE_EDGE,
                    source_event_id="E0",
                )
            ],
            motivating_event_ids=["E0"],
        )
        self.assertEqual(proposal.motivating_event_ids, [report.predicted_top1])


if __name__ == "__main__":
    unittest.main()
