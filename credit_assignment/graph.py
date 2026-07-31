"""LangGraph wiring for the software generation pipeline."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from credit_assignment.fault_injection import FaultInjector, PoisonMode
from credit_assignment.nodes import (
    coder_node,
    executor_node,
    planner_node,
    reviser_node,
    reviewer_node,
)
from credit_assignment.state import AgentState


def build_pipeline_graph():
    """
    Pipeline: Planner → Coder → Reviewer → Reviser → Executor.

    Reviser is a coder follow-up that applies review feedback (critical for
    POISON_REVIEWER's active destructive edit). It is not a separate Shapley agent.
    """
    graph = StateGraph(AgentState)
    graph.add_node("planner", planner_node)
    graph.add_node("coder", coder_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("reviser", reviser_node)
    graph.add_node("executor", executor_node)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "coder")
    graph.add_edge("coder", "reviewer")
    graph.add_edge("reviewer", "reviser")
    graph.add_edge("reviser", "executor")
    graph.add_edge("executor", END)

    return graph.compile()


# Module-level compiled graph (base production pipeline)
BASE_GRAPH = build_pipeline_graph()


def run_pipeline(
    task_description: str,
    *,
    fault_injector: FaultInjector | None = None,
    active_agents: list[str] | None = None,
    prompt_overrides: dict[str, str] | None = None,
    entry_point: str = "solve",
    test_cases: list[dict[str, Any]] | None = None,
    reference_solution: str = "",
    edge_interventions: list[dict[str, str]] | None = None,
) -> AgentState:
    """
    Execute one full pipeline run and return a validated AgentState.

    edge_interventions: optional Week 6 live prune/weaken gates
    (list of {source_event_id, target_event_id, kind}).
    """
    injector = fault_injector or FaultInjector(mode=PoisonMode.NONE)
    initial: dict[str, Any] = {
        "task_description": task_description,
        "plan": "",
        "code": "",
        "review_status": "",
        "review_feedback": "",
        "execution_result": "",
        "trace_log": {},
        "global_reward": 0.0,
        "poison_mode": injector.mode.value,
        "poisoned_node": injector.mode.target_node,
        "active_agents": active_agents
        or ["planner", "coder", "reviewer", "executor"],
        "prompt_overrides": prompt_overrides or {},
        "entry_point": entry_point,
        "test_cases": test_cases or [],
        "reference_solution": reference_solution,
        "edge_interventions": list(edge_interventions or []),
    }
    raw = BASE_GRAPH.invoke(initial)
    if isinstance(raw, AgentState):
        return raw
    return AgentState.model_validate(raw)
