"""Shared attribution report schema and engine protocol."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from commscm.schema.events import RunTrace


class CRRankRow(BaseModel):
    rank: int
    event_id: str
    channel: str
    cr: float
    delta_y: float
    factual_reward: float
    counterfactual_reward: float
    recomputed_count: int
    runtime_ms: float

    model_config = {"extra": "forbid"}


class AttributionReport(BaseModel):
    run_id: str
    engine_name: str
    factual_reward: float
    rows: list[CRRankRow]
    total_runtime_ms: float
    predicted_top1: str | None = None
    gold_fault_event_id: str | None = None
    hit_at_1: bool | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class AttributionEngine(Protocol):
    def score(self, trace: RunTrace) -> AttributionReport:
        ...
