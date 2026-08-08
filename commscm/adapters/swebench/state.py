"""Adapter-local SWE-bench pipeline state (not Part I schema)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SWEBenchPipelineState(BaseModel):
    instance_id: str = ""
    problem_statement: str = ""
    repo: str = ""
    plan: str = ""
    patch_attempt: str = ""
    review_status: str = ""
    review_feedback: str = ""
    execution_result: str = ""
    global_reward: float = Field(default=0.0, ge=0.0, le=1.0)
    poison_mode: str = "NONE"
    poisoned_node: str | None = None
    gold_patch: str = ""
    fail_to_pass: list[str] = Field(default_factory=list)
    trace_log: dict[str, Any] = Field(default_factory=dict)
    edge_interventions: list[dict[str, str]] = Field(default_factory=list)

    model_config = {"extra": "forbid"}
