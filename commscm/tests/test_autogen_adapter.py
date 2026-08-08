"""Stage 1 unit tests: AutoGen adapter → RunTrace without touching CommSCM core."""

from __future__ import annotations

import unittest

from credit_assignment.fault_injection import IMPOSSIBLE_CONSTRAINT_MARKER, SYNTAX_ERROR_MARKER
from commscm.adapters.autogen.extract import (
    autogen_reward_outcome,
    autogen_state_to_run_trace,
    gold_event_for_poison,
)
from commscm.adapters.autogen.state import AutoGenPipelineState
from commscm.schema.events import Channel


class TestAutogenExtract(unittest.TestCase):
    def _poisoned_planner_state(self) -> AutoGenPipelineState:
        plan = f"step 1\n{IMPOSSIBLE_CONSTRAINT_MARKER}"
        return AutoGenPipelineState(
            task_description="Write solve() that returns 'ok'",
            plan=plan,
            code="def solve():\n    return 'ok'\n",
            review_status="Rejected",
            review_feedback="bad plan",
            execution_result="FAIL: impossible constraint",
            global_reward=0.1,
            poison_mode="POISON_PLANNER",
            poisoned_node="planner",
            trace_log={
                "planner": {"output": plan, "latency_ms": 1.0, "poisoned": True},
                "coder": {"output": "def solve():\n    return 'ok'\n", "latency_ms": 1.0},
                "reviewer": {"output": "VERDICT: Rejected\nstatus=Rejected", "latency_ms": 1.0},
                "reviser": {"output": "passthrough", "latency_ms": 0.1},
                "executor": {"output": "FAIL", "latency_ms": 0.5, "reward": 0.1},
            },
            autogen_messages=[
                {"source": "planner", "type": "TextMessage", "content": plan},
            ],
        )

    def test_schema_and_topology(self):
        tr = autogen_state_to_run_trace(self._poisoned_planner_state(), run_id="t1")
        self.assertEqual(set(tr.dag.events), {"C0", "C1", "C2", "C3", "C4", "C5"})
        self.assertEqual(tr.dag.events["C2"].parents, ["C1"])
        self.assertEqual(tr.dag.events["C4"].parents, ["C3", "C2"])
        self.assertEqual(tr.dag.events["C5"].channel, Channel.TOOL)
        self.assertEqual(tr.gold_fault_event_id, "C1")
        self.assertEqual(tr.extra.get("framework"), "autogen_agentchat")
        self.assertTrue(tr.dag.events["C1"].meta.get("poisoned"))

    def test_gold_map(self):
        self.assertEqual(gold_event_for_poison("coder"), "C2")
        self.assertEqual(gold_event_for_poison("reviewer"), "C3")

    def test_reward_outcome_markers(self):
        tr = autogen_state_to_run_trace(self._poisoned_planner_state(), run_id="t2")
        self.assertEqual(autogen_reward_outcome(tr.dag), 0.0)
        # Clean DAG
        clean = AutoGenPipelineState(
            task_description="t",
            plan="ok plan",
            code="def solve():\n    return 'ok'\n",
            review_status="Approved",
            execution_result="PASS",
            global_reward=1.0,
            trace_log={
                "planner": {"output": "ok plan"},
                "coder": {"output": "def solve():\n    return 'ok'\n"},
                "reviewer": {"output": "VERDICT: Approved"},
                "reviser": {"output": "passthrough"},
                "executor": {"output": "PASS"},
            },
        )
        tr2 = autogen_state_to_run_trace(clean, run_id="t3")
        self.assertEqual(autogen_reward_outcome(tr2.dag), 1.0)

    def test_frozen_engine_consumes_trace(self):
        """Stage 1 success: frozen attribution engine accepts adapter RunTrace."""
        from commscm.attribution.subset import SubsetAttributionEngine
        from commscm.estimators.replay import DescendantReplayEngine
        from commscm.adapters.autogen.mechanisms import make_autogen_sticky_registry

        tr = autogen_state_to_run_trace(self._poisoned_planner_state(), run_id="t4")
        mechs = make_autogen_sticky_registry(tr.dag)
        engine = SubsetAttributionEngine(
            DescendantReplayEngine(autogen_reward_outcome, mechs, structural_cost_iters=0),
            {"C1", "C2", "C3", "C4", "C5"},
            name="AutoGenCR",
        )
        report = engine.score(tr)
        self.assertEqual(report.predicted_top1, "C1")
        self.assertLess(report.factual_reward, 1.0)


if __name__ == "__main__":
    unittest.main()
