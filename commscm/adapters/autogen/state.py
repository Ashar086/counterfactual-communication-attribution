"""
Recorded AutoGen pipeline state — adapter-local, not Part I schema.

Mirrors the LangGraph role topology for fair Stage-3 comparison, but is
produced only by AutoGen AgentChat sequential execution.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AutoGenPipelineState(BaseModel):
    """Artifacts + per-role message log from one AutoGen sequential run."""

    task_description: str = ""
    plan: str = ""
    code: str = ""
    review_status: str = ""
    review_feedback: str = ""
    execution_result: str = ""
    global_reward: float = Field(default=0.0, ge=0.0, le=1.0)
    poison_mode: str = "NONE"
    poisoned_node: str | None = None
    entry_point: str = "solve"
    # Per-role: {output, latency_ms, poisoned?, model?, source_messages?}
    trace_log: dict[str, Any] = Field(default_factory=dict)
    # Raw AutoGen chat messages (framework-native), opaque to CommSCM core
    autogen_messages: list[dict[str, Any]] = Field(default_factory=list)
    edge_interventions: list[dict[str, str]] = Field(default_factory=list)

    model_config = {"extra": "forbid"}
