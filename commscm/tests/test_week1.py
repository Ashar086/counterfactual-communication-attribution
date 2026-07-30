"""Week-1 unit tests: schema, soft interventions, trace I/O, CR helper."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from commscm.attribution import cr_from_estimates, rank_by_cr
from commscm.interventions import SoftIntervention, apply_soft_intervention
from commscm.runtime import read_trace_json, write_trace_json
from commscm.schema import Channel, CommunicationEvent, EventDAG, RunOutcome, RunTrace


def _toy_dag() -> EventDAG:
    dag = EventDAG()
    dag.add(
        CommunicationEvent(
            event_id="e0",
            sender="user",
            receiver="planner",
            channel=Channel.TEXT,
            message="Write add(a,b)",
            time_index=0,
        )
    )
    dag.add(
        CommunicationEvent(
            event_id="e1",
            sender="planner",
            receiver="coder",
            channel=Channel.TEXT,
            message="IMPOSSIBLE_CONSTRAINT: O(1) NP-hard",
            time_index=1,
            parents=["e0"],
        )
    )
    dag.add(
        CommunicationEvent(
            event_id="e2",
            sender="coder",
            receiver="executor",
            channel=Channel.TEXT,
            message="def add(a,b): return a+b",
            time_index=2,
            parents=["e1"],
        )
    )
    return dag


class SchemaTests(unittest.TestCase):
    def test_topo_order(self) -> None:
        self.assertEqual(_toy_dag().topological_order(), ["e0", "e1", "e2"])

    def test_rejects_missing_parent(self) -> None:
        dag = EventDAG()
        with self.assertRaises(ValueError):
            dag.add(
                CommunicationEvent(
                    event_id="x",
                    sender="a",
                    receiver="b",
                    channel=Channel.TEXT,
                    message="hi",
                    time_index=0,
                    parents=["missing"],
                )
            )


class InterventionTests(unittest.TestCase):
    def test_soft_null_preserves_identity(self) -> None:
        dag = _toy_dag()
        out = apply_soft_intervention(
            dag, SoftIntervention(event_id="e1", use_channel_null=True)
        )
        self.assertIn("e1", out.events)
        self.assertEqual(out.events["e1"].sender, "planner")
        self.assertIn("NULL_TEXT", out.events["e1"].message)
        self.assertNotEqual(out.events["e1"].message, dag.events["e1"].message)
        # factual DAG unchanged
        self.assertIn("IMPOSSIBLE", dag.events["e1"].message)

    def test_tool_null_template(self) -> None:
        dag = EventDAG()
        dag.add(
            CommunicationEvent(
                event_id="t0",
                sender="agent",
                receiver="env",
                channel=Channel.TOOL,
                message='{"tool":"bash","args":{"cmd":"rm -rf /"}}',
                time_index=0,
            )
        )
        out = apply_soft_intervention(dag, SoftIntervention(event_id="t0"))
        self.assertIn("null", out.events["t0"].message)


class TraceIOTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        tr = RunTrace(
            run_id="r1",
            task_id="add",
            dag=_toy_dag(),
            outcome=RunOutcome(reward=0.1, success=False),
            gold_fault_event_id="e1",
            poison_mode="POISON_PLANNER",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.json"
            write_trace_json(tr, path)
            loaded = read_trace_json(path)
        self.assertEqual(loaded.gold_fault_event_id, "e1")
        self.assertEqual(loaded.dag.events["e1"].channel, Channel.TEXT)


class CRTests(unittest.TestCase):
    def test_rank(self) -> None:
        scores = [
            cr_from_estimates(
                event_id="e2", channel="text", factual_reward=0.1, counterfactual_reward=0.2
            ),
            cr_from_estimates(
                event_id="e1", channel="text", factual_reward=0.1, counterfactual_reward=1.0
            ),
        ]
        ranked = rank_by_cr(scores)
        self.assertEqual(ranked[0].event_id, "e1")
        self.assertAlmostEqual(ranked[0].meta["delta_y"], 0.9)
        self.assertAlmostEqual(ranked[0].cr, -0.9)


if __name__ == "__main__":
    unittest.main()
