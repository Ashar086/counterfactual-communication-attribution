"""Adapter-local WebArena pipeline state (not Part I schema)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WebArenaPipelineState(BaseModel):
    task_id: str = ""
    intent: str = ""
    sites: list[str] = Field(default_factory=list)
    plan: str = ""
    navigation_attempt: str = ""
    review_status: str = ""
    review_feedback: str = ""
    revised_navigation: str = ""
    execution_result: str = ""
    global_reward: float = Field(default=0.0, ge=0.0, le=1.0)
    official_success: float | None = None
    poison_mode: str = "NONE"
    poisoned_node: str | None = None
    trace_log: dict[str, Any] = Field(default_factory=dict)
    edge_interventions: list[dict[str, str]] = Field(default_factory=list)
    env_mode: str = "offline_fixture"

    model_config = {"extra": "forbid"}
