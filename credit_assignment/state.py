"""Shared state schema for the compound agentic pipeline."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, Field


def merge_trace_logs(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    """Reducer: shallow-merge per-node trace entries across graph steps."""
    merged: dict[str, Any] = dict(left or {})
    merged.update(right or {})
    return merged


class AgentState(BaseModel):
    """Pipeline state carried through Planner → Coder → Reviewer → Executor."""

    task_description: str = ""
    plan: str = ""
    code: str = ""
    review_status: str = ""
    execution_result: str = ""
    trace_log: Annotated[dict[str, Any], merge_trace_logs] = Field(default_factory=dict)
    global_reward: float = Field(default=0.0, ge=0.0, le=1.0)
    # Ground-truth / config fields (set at invoke time, preserved through the graph)
    poison_mode: str = "NONE"
    poisoned_node: str | None = None
    active_agents: list[str] = Field(
        default_factory=lambda: ["planner", "coder", "reviewer", "executor"]
    )
    prompt_overrides: dict[str, str] = Field(default_factory=dict)
    # Sandbox inputs
    entry_point: str = "solve"
    test_cases: list[dict[str, Any]] = Field(default_factory=list)
    reference_solution: str = ""
    review_feedback: str = ""

    model_config = {"extra": "forbid"}
