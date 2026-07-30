"""Attribution scoring engines using replay backends."""

from __future__ import annotations

import time
from typing import Any

from commscm.attribution.report import AttributionEngine, AttributionReport, CRRankRow
from commscm.attribution.responsibility import CommunicationResponsibility
from commscm.estimators.replay import (
    CachedDescendantReplayEngine,
    CostBreakdown,
    DescendantReplayEngine,
    FullReplayEngine,
    ReplayEngineBase,
    ReplayResult,
)
from commscm.interventions.soft import SoftIntervention
from commscm.schema.events import RunTrace


class ReplayAttributionEngine:
    def __init__(self, replay_engine: ReplayEngineBase, *, name: str) -> None:
        self.replay_engine = replay_engine
        self.name = name

    def score(self, trace: RunTrace) -> AttributionReport:
        t0 = time.perf_counter()
        y_f = self.replay_engine.factual_reward(trace)
        replays: dict[str, ReplayResult] = {}
        scores: list[CommunicationResponsibility] = []
        cost_total = CostBreakdown()
        for eid in trace.dag.topological_order():
            ev = trace.dag.events[eid]
            intervention = SoftIntervention(
                event_id=eid,
                use_channel_null=True,
                nulls=self.replay_engine.nulls,
                tag=self.name,
            )
            result = self.replay_engine.replay(trace, intervention)
            replays[eid] = result
            cost_total = cost_total.add(result.cost)
            delta_y = result.counterfactual_reward - result.factual_reward
            cr = result.factual_reward - result.counterfactual_reward
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
                        "structural_evals": result.cost.structural_evals,
                    },
                )
            )
        scores_sorted = sorted(scores, key=lambda s: (-float(s.meta["delta_y"]), s.event_id))
        rows = [
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
            for i, s in enumerate(scores_sorted, start=1)
        ]
        top1 = rows[0].event_id if rows else None
        gold = trace.gold_fault_event_id
        return AttributionReport(
            run_id=trace.run_id,
            engine_name=self.name,
            factual_reward=y_f,
            rows=rows,
            total_runtime_ms=round((time.perf_counter() - t0) * 1000, 3),
            predicted_top1=top1,
            gold_fault_event_id=gold,
            hit_at_1=(top1 == gold) if gold else None,
            extra={
                "gold_fault_event_ids": list(trace.gold_fault_event_ids),
                "cost_breakdown": cost_total.model_dump(mode="json"),
                "replay_details": {
                    eid: {
                        "runtime_ms": rp.runtime_ms,
                        "recomputed_count": len(rp.recomputed_event_ids),
                        "cost": rp.cost.model_dump(mode="json"),
                    }
                    for eid, rp in replays.items()
                },
            },
        )


class ExactReplayOracle(ReplayAttributionEngine):
    def __init__(self, replay_engine: FullReplayEngine) -> None:
        super().__init__(replay_engine, name="ExactReplayOracle")


class DescendantReplayEstimator(ReplayAttributionEngine):
    def __init__(self, replay_engine: DescendantReplayEngine) -> None:
        super().__init__(replay_engine, name="DescendantReplayEstimator")


class CachedReplayEstimator(ReplayAttributionEngine):
    def __init__(self, replay_engine: CachedDescendantReplayEngine) -> None:
        super().__init__(replay_engine, name="CachedReplayEstimator")
