"""
Extract CommSCM RunTraces from the LangGraph credit_assignment pipeline.

Week 5: attribution only — no CCAS edits. Does not modify Part I/II algorithms.
"""

from __future__ import annotations

from typing import Any

from credit_assignment.state import AgentState
from commscm.schema.events import Channel, CommunicationEvent, EventDAG, RunOutcome, RunTrace

# Node → channel for typed soft interventions
_CHANNEL = {
    "task": Channel.TEXT,
    "planner": Channel.TEXT,
    "coder": Channel.TEXT,
    "reviewer": Channel.TEXT,
    "reviser": Channel.TEXT,
    "executor": Channel.TOOL,
}

_NODE_TO_EVENT = {
    "planner": "C1",
    "coder": "C2",
    "reviewer": "C3",
    "reviser": "C4",
    "executor": "C5",
}


def gold_event_for_poison(poisoned_node: str | None) -> str | None:
    if not poisoned_node:
        return None
    return _NODE_TO_EVENT.get(poisoned_node)


def agent_state_to_run_trace(
    state: AgentState,
    *,
    run_id: str,
    task_id: str = "langgraph_pipeline",
) -> RunTrace:
    """
    Map one LangGraph pipeline state to a time-indexed communication DAG.

    Topology (fixed):
      C0 task → C1 plan → C2 code → C3 review → C4 revised code → C5 execution
    """
    trace_log = state.trace_log or {}

    def _out(node: str, fallback: str) -> str:
        entry = trace_log.get(node) or {}
        if isinstance(entry, dict) and entry.get("output") is not None:
            return str(entry["output"])
        return fallback

    messages = {
        "C0": state.task_description,
        "C1": _out("planner", state.plan),
        "C2": _out("coder", state.code),
        "C3": _out("reviewer", f"{state.review_status}\n{state.review_feedback}".strip()),
        "C4": _out("reviser", state.code),
        "C5": _out("executor", state.execution_result),
    }
    parents = {
        "C0": [],
        "C1": ["C0"],
        "C2": ["C1"],
        "C3": ["C2"],
        "C4": ["C3", "C2"],
        "C5": ["C4"],
    }
    senders = {
        "C0": "user",
        "C1": "planner",
        "C2": "coder",
        "C3": "reviewer",
        "C4": "reviser",
        "C5": "executor",
    }
    receivers = {
        "C0": "planner",
        "C1": "coder",
        "C2": "reviewer",
        "C3": "reviser",
        "C4": "executor",
        "C5": "user",
    }
    channels = {
        "C0": Channel.TEXT,
        "C1": Channel.TEXT,
        "C2": Channel.TEXT,
        "C3": Channel.TEXT,
        "C4": Channel.TEXT,
        "C5": Channel.TOOL,
    }

    dag = EventDAG()
    order = ["C0", "C1", "C2", "C3", "C4", "C5"]
    node_key = {
        "C1": "planner",
        "C2": "coder",
        "C3": "reviewer",
        "C4": "reviser",
        "C5": "executor",
    }
    for i, eid in enumerate(order):
        meta: dict[str, Any] = {"langgraph_node": senders[eid]}
        nk = node_key.get(eid)
        if nk and isinstance(trace_log.get(nk), dict):
            meta["latency_ms"] = trace_log[nk].get("latency_ms")
            meta["poisoned"] = bool(trace_log[nk].get("poisoned"))
        dag.add(
            CommunicationEvent(
                event_id=eid,
                sender=senders[eid],
                receiver=receivers[eid],
                channel=channels[eid],
                message=messages[eid],
                time_index=i,
                parents=list(parents[eid]),
                meta=meta,
            )
        )

    gold = gold_event_for_poison(state.poisoned_node)
    reward = float(state.global_reward)
    return RunTrace(
        run_id=run_id,
        task_id=task_id,
        architecture_id="langgraph_planner_coder_reviewer_reviser_executor_v0",
        dag=dag,
        outcome=RunOutcome(
            reward=reward,
            success=reward >= 1.0,
            metrics={
                "poison_mode": state.poison_mode,
                "poisoned_node": state.poisoned_node,
            },
        ),
        gold_fault_event_id=gold,
        gold_fault_event_ids=[gold] if gold else [],
        poison_mode=state.poison_mode,
        extra={
            "source": "credit_assignment.AgentState",
            "poisoned_node": state.poisoned_node,
            "event_map": dict(_NODE_TO_EVENT),
        },
    )


def langgraph_reward_outcome(dag) -> float:
    """
    Deterministic Week-5 outcome proxy for soft-null replay.

    Uses fault markers from the LangGraph injector (channel-native content).
    Does not call the LLM.
    """
    from credit_assignment.fault_injection import (
        DESTRUCTIVE_REVIEW_MARKER,
        IMPOSSIBLE_CONSTRAINT_MARKER,
        INFINITE_LOOP_MARKER,
        SYNTAX_ERROR_MARKER,
    )

    markers = (
        IMPOSSIBLE_CONSTRAINT_MARKER,
        SYNTAX_ERROR_MARKER,
        DESTRUCTIVE_REVIEW_MARKER,
        INFINITE_LOOP_MARKER,
        "FAULT_",
    )
    for e in dag.events.values():
        msg = e.message or ""
        if any(m in msg for m in markers):
            return 0.0
    return 1.0
