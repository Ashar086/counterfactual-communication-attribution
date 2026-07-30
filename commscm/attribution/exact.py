"""Exact Communication Responsibility via full soft-null sweep."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

from commscm.attribution.responsibility import CommunicationResponsibility
from commscm.estimators.exact_replay import ExactReplayEngine, ReplayResult
from commscm.interventions.soft import SoftIntervention
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


class ExactAttributionReport(BaseModel):
    run_id: str
    factual_reward: float
    rows: list[CRRankRow]
    total_runtime_ms: float
    predicted_top1: str | None = None
    gold_fault_event_id: str | None = None
    hit_at_1: bool | None = None
    replays: dict[str, ReplayResult] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


def attribute_exact(
    trace: RunTrace,
    engine: ExactReplayEngine,
    *,
    event_ids: list[str] | None = None,
) -> ExactAttributionReport:
    """
    Exact CR for each event via typed soft null replay.

    Week-2 convention:
        CR(k)  = Y_factual - Y_counterfactual
        ΔY(k)  = Y_counterfactual - Y_factual
    Rank by ΔY descending (largest improvement when nulled ⇒ top blame).
    """
    t0 = time.perf_counter()
    y_f = engine.factual_reward(trace)
    targets = event_ids or list(trace.dag.topological_order())
    scores: list[CommunicationResponsibility] = []
    replays: dict[str, ReplayResult] = {}

    for eid in targets:
        ev = trace.dag.events[eid]
        intervention = SoftIntervention(
            event_id=eid,
            use_channel_null=True,
            nulls=engine.nulls,
            tag="exact_soft_null",
        )
        result = engine.replay(trace, intervention)
        replays[eid] = result
        cr = result.factual_reward - result.counterfactual_reward
        delta_y = result.counterfactual_reward - result.factual_reward
        scores.append(
            CommunicationResponsibility(
                event_id=eid,
                channel=ev.channel.value,
                factual_reward=result.factual_reward,
                counterfactual_reward=result.counterfactual_reward,
                cr=cr,
                meta={
                    "delta_y": delta_y,
                    "recomputed_count": len(result.recomputed_event_ids),
                    "runtime_ms": result.runtime_ms,
                },
            )
        )

    # Rank: higher ΔY first; tie-break lower event_id for determinism
    scores_sorted = sorted(
        scores,
        key=lambda s: (-float(s.meta["delta_y"]), s.event_id),
    )

    rows: list[CRRankRow] = []
    for i, s in enumerate(scores_sorted, start=1):
        rows.append(
            CRRankRow(
                rank=i,
                event_id=s.event_id,
                channel=s.channel,
                cr=s.cr,
                delta_y=float(s.meta["delta_y"]),
                factual_reward=s.factual_reward,
                counterfactual_reward=s.counterfactual_reward,
                recomputed_count=int(s.meta["recomputed_count"]),
                runtime_ms=float(s.meta["runtime_ms"]),
            )
        )

    top1 = rows[0].event_id if rows else None
    gold = trace.gold_fault_event_id
    hit = (top1 == gold) if gold else None
    total_ms = round((time.perf_counter() - t0) * 1000, 3)

    return ExactAttributionReport(
        run_id=trace.run_id,
        factual_reward=y_f,
        rows=rows,
        total_runtime_ms=total_ms,
        predicted_top1=top1,
        gold_fault_event_id=gold,
        hit_at_1=hit,
        replays=replays,
    )
