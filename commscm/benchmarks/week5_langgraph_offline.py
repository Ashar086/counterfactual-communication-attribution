"""Offline LangGraph-shaped AgentStates for Week-5 extractor/attribution tests."""

from __future__ import annotations

from credit_assignment.fault_injection import (
    DESTRUCTIVE_REVIEW_MARKER,
    IMPOSSIBLE_CONSTRAINT_MARKER,
    SYNTAX_ERROR_MARKER,
    PoisonMode,
)
from credit_assignment.state import AgentState


def make_offline_poisoned_state(mode: PoisonMode, *, task: str = "add(a,b)") -> AgentState:
    """Deterministic AgentState with injector markers (no LLM)."""
    plan = "Plan: implement add"
    code = "def add(a,b):\n    return a+b\n"
    review = "VERDICT: Approve\nLooks good."
    revised = code
    execution = "passed"
    reward = 1.0
    poisoned = mode.target_node

    if mode == PoisonMode.POISON_PLANNER:
        plan = f"{plan}\n\n{IMPOSSIBLE_CONSTRAINT_MARKER}"
        reward = 0.0
        execution = "failed"
    elif mode == PoisonMode.POISON_CODER:
        code = f"{code}\n{SYNTAX_ERROR_MARKER}\n"
        revised = code
        reward = 0.0
        execution = "failed"
    elif mode == PoisonMode.POISON_REVIEWER:
        # Channel-native fault on the review event only (advice marker).
        # Keep revised code clean so localization targets C3, not the symptom on C4.
        review = (
            f"{DESTRUCTIVE_REVIEW_MARKER}\n"
            "VERDICT: NeedsRevision\nReplace loop with while True."
        )
        revised = code
        reward = 0.0
        execution = "failed_due_to_bad_review_advice"

    return AgentState(
        task_description=task,
        plan=plan,
        code=code,
        review_status="NeedsRevision" if mode == PoisonMode.POISON_REVIEWER else "Approve",
        review_feedback=review,
        execution_result=execution,
        global_reward=reward,
        poison_mode=mode.value,
        poisoned_node=poisoned,
        trace_log={
            "planner": {"output": plan, "latency_ms": 1.0, "poisoned": mode == PoisonMode.POISON_PLANNER},
            "coder": {"output": code, "latency_ms": 1.0, "poisoned": mode == PoisonMode.POISON_CODER},
            "reviewer": {"output": review, "latency_ms": 1.0, "poisoned": mode == PoisonMode.POISON_REVIEWER},
            "reviser": {"output": revised, "latency_ms": 1.0, "poisoned": False},
            "executor": {"output": execution, "latency_ms": 1.0, "poisoned": False},
        },
    )


def build_offline_langgraph_dataset() -> list[AgentState]:
    return [
        make_offline_poisoned_state(PoisonMode.POISON_PLANNER),
        make_offline_poisoned_state(PoisonMode.POISON_CODER),
        make_offline_poisoned_state(PoisonMode.POISON_REVIEWER),
    ]
