"""
Map SWEBenchPipelineState → CommSCM RunTrace.

Isomorphic C0–C5 topology to LangGraph / AutoGen extractors.
Benchmark-specific metadata only in ``meta`` / ``extra``.
"""

from __future__ import annotations

from typing import Any

from commscm.adapters.swebench.state import SWEBenchPipelineState
from commscm.schema.events import Channel, CommunicationEvent, EventDAG, RunOutcome, RunTrace

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


def swebench_state_to_run_trace(
    state: SWEBenchPipelineState,
    *,
    run_id: str,
    task_id: str | None = None,
) -> RunTrace:
    """
    Topology (fixed, isomorphic to Parts IV–V):
      C0 task → C1 plan → C2 patch → C3 review → C4 revised → C5 score
    """
    tid = task_id or state.instance_id or "swebench"
    trace_log = state.trace_log or {}

    def _out(node: str, fallback: str) -> str:
        entry = trace_log.get(node) or {}
        if isinstance(entry, dict) and entry.get("output") is not None:
            return str(entry["output"])
        return fallback

    messages = {
        "C0": state.problem_statement,
        "C1": _out("planner", state.plan),
        "C2": _out("coder", state.patch_attempt),
        "C3": _out("reviewer", f"{state.review_status}\n{state.review_feedback}".strip()),
        "C4": _out("reviser", state.patch_attempt),
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
        meta: dict[str, Any] = {
            "swebench_agent": senders[eid],
            "framework": "swebench_shaped",
            "instance_id": state.instance_id,
        }
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
        task_id=tid,
        architecture_id="swebench_shaped_planner_coder_reviewer_reviser_executor_v0",
        dag=dag,
        outcome=RunOutcome(
            reward=reward,
            success=reward >= 1.0,
            metrics={
                "poison_mode": state.poison_mode,
                "poisoned_node": state.poisoned_node,
                "repo": state.repo,
            },
        ),
        gold_fault_event_id=gold,
        gold_fault_event_ids=[gold] if gold else [],
        poison_mode=state.poison_mode,
        extra={
            "source": "commscm.adapters.swebench.SWEBenchPipelineState",
            "framework": "swebench_shaped",
            "benchmark": "princeton-nlp/SWE-bench_Verified",
            "scope_note": (
                "SWE-bench Verified–shaped: problem statements + communication poisons; "
                "not official Docker resolve@1"
            ),
            "poisoned_node": state.poisoned_node,
            "event_map": dict(_NODE_TO_EVENT),
            "instance_id": state.instance_id,
        },
    )


def swebench_reward_outcome(dag) -> float:
    """
    Deterministic outcome proxy for soft-null replay (adapter-local).

    Same fault markers as LangGraph / AutoGen so CR compares fairly.
    Does not call the LLM. Does not modify Part I/II.
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
