"""Unit tests: WebArena adapter → RunTrace without touching CommSCM core."""

from __future__ import annotations

import unittest

from credit_assignment.fault_injection import IMPOSSIBLE_CONSTRAINT_MARKER
from commscm.adapters.webarena.extract import (
    GOLD_EDGE,
    gold_event_for_poison,
    webarena_reward_outcome,
    webarena_state_to_run_trace,
)
from commscm.adapters.webarena.load import load_vi_c_instance_list, load_webarena_instance
from commscm.adapters.webarena.state import WebArenaPipelineState
from commscm.schema.events import Channel


class TestWebArenaExtract(unittest.TestCase):
    def _poisoned_planner_state(self) -> WebArenaPipelineState:
        plan = f"step 1\n{IMPOSSIBLE_CONSTRAINT_MARKER}"
        return WebArenaPipelineState(
            task_id="743",
            intent="Find cheapest headphones",
            sites=["shopping"],
            plan=plan,
            navigation_attempt="goto shopping\nclick headphones\n",
            review_status="Rejected",
            review_feedback="bad plan",
            revised_navigation="goto shopping\nclick headphones\n",
            execution_result="FAIL: impossible constraint",
            global_reward=0.0,
            poison_mode="POISON_PLANNER",
            poisoned_node="planner",
            trace_log={
                "planner": {"output": plan, "latency_ms": 1.0, "poisoned": True},
                "navigator": {
                    "output": "goto shopping\nclick headphones\n",
                    "latency_ms": 1.0,
                },
                "critic": {"output": "VERDICT: Rejected\nstatus=Rejected", "latency_ms": 1.0},
                "reviser": {"output": "passthrough", "latency_ms": 0.1},
                "executor": {"output": "FAIL", "latency_ms": 0.5, "reward": 0.0},
            },
            env_mode="offline_fixture",
        )

    def test_schema_and_topology(self):
        tr = webarena_state_to_run_trace(self._poisoned_planner_state(), run_id="t1")
        self.assertEqual(set(tr.dag.events), {"C0", "C1", "C2", "C3", "C4", "C5"})
        self.assertEqual(tr.dag.events["C2"].parents, ["C1"])
        self.assertEqual(tr.dag.events["C4"].parents, ["C3", "C2"])
        self.assertEqual(tr.dag.events["C2"].channel, Channel.TOOL)
        self.assertEqual(tr.gold_fault_event_id, "C1")
        self.assertEqual(tr.extra.get("gold_edge"), list(GOLD_EDGE))
        self.assertEqual(tr.extra.get("framework"), "webarena_adapter")
        self.assertTrue(tr.dag.events["C1"].meta.get("poisoned"))

    def test_gold_map(self):
        self.assertEqual(gold_event_for_poison("planner"), "C1")
        self.assertEqual(gold_event_for_poison("navigator"), "C2")
        self.assertEqual(gold_event_for_poison("critic"), "C3")

    def test_reward_outcome_markers(self):
        tr = webarena_state_to_run_trace(self._poisoned_planner_state(), run_id="t2")
        self.assertEqual(webarena_reward_outcome(tr.dag), 0.0)

    def test_instance_list_and_fixture(self):
        ids = load_vi_c_instance_list()
        self.assertEqual(len(ids), 100)
        self.assertEqual(ids[:5], [743, 419, 231, 619, 614])
        inst = load_webarena_instance(743)
        self.assertEqual(inst.task_id, "743")
        self.assertIn("headphones", inst.intent.lower())
        self.assertEqual(inst.source, "offline_fixture")

    def test_frozen_engine_consumes_trace(self):
        from commscm.adapters.webarena.mechanisms import make_webarena_sticky_registry
        from commscm.attribution.subset import SubsetAttributionEngine
        from commscm.estimators.replay import DescendantReplayEngine

        tr = webarena_state_to_run_trace(self._poisoned_planner_state(), run_id="t3")
        report = SubsetAttributionEngine(
            DescendantReplayEngine(
                webarena_reward_outcome,
                make_webarena_sticky_registry(tr.dag),
                structural_cost_iters=0,
            ),
            {"C1", "C2", "C3", "C4", "C5"},
            name="WebArenaCR",
        ).score(tr)
        self.assertEqual(report.predicted_top1, "C1")


if __name__ == "__main__":
    unittest.main()
