"""Week-5 LangGraph extractor + attribution-only tests."""

from __future__ import annotations

import unittest

from credit_assignment.fault_injection import PoisonMode
from commscm.attribution.subset import SubsetAttributionEngine
from commscm.benchmarks.week5_langgraph_offline import make_offline_poisoned_state
from commscm.estimators.replay import DescendantReplayEngine
from commscm.traces.langgraph_extract import (
    agent_state_to_run_trace,
    gold_event_for_poison,
    langgraph_reward_outcome,
)
from commscm.traces.langgraph_mechanisms import make_langgraph_sticky_registry

AGENT_EVENTS = {"C1", "C2", "C3", "C4", "C5"}


def _score(tr):
    return SubsetAttributionEngine(
        DescendantReplayEngine(
            langgraph_reward_outcome,
            make_langgraph_sticky_registry(tr.dag),
        ),
        AGENT_EVENTS,
        name="LangGraphCR",
    ).score(tr)


class Week5LangGraphTests(unittest.TestCase):
    def test_extractor_maps_poison_to_gold_event(self) -> None:
        st = make_offline_poisoned_state(PoisonMode.POISON_PLANNER)
        tr = agent_state_to_run_trace(st, run_id="t0")
        self.assertEqual(tr.gold_fault_event_id, "C1")
        self.assertEqual(len(tr.dag.events), 6)

    def test_cr_localizes_planner_poison(self) -> None:
        tr = agent_state_to_run_trace(
            make_offline_poisoned_state(PoisonMode.POISON_PLANNER), run_id="t1"
        )
        self.assertEqual(_score(tr).predicted_top1, "C1")

    def test_cr_localizes_coder_poison(self) -> None:
        tr = agent_state_to_run_trace(
            make_offline_poisoned_state(PoisonMode.POISON_CODER), run_id="t2"
        )
        self.assertEqual(_score(tr).predicted_top1, gold_event_for_poison("coder"))

    def test_cr_localizes_reviewer_poison(self) -> None:
        tr = agent_state_to_run_trace(
            make_offline_poisoned_state(PoisonMode.POISON_REVIEWER), run_id="t3"
        )
        self.assertEqual(_score(tr).predicted_top1, "C3")


if __name__ == "__main__":
    unittest.main()
