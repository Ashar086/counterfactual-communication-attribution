"""Attribution helper: score only a subset of event ids (Week 5 agent nodes)."""

from __future__ import annotations

import time

from commscm.attribution.engines import ReplayAttributionEngine
from commscm.attribution.report import AttributionReport, CRRankRow
from commscm.attribution.responsibility import CommunicationResponsibility
from commscm.estimators.replay import CostBreakdown, ReplayEngineBase
from commscm.interventions.soft import SoftIntervention
from commscm.schema.events import RunTrace


class SubsetAttributionEngine:
    """
    Wraps a replay backend but only intervenes on `event_ids`.

    Used to exclude exogenous task nodes (C0) from LangGraph localization.
    Does not change soft-null or CR definitions.
    """

    def __init__(
        self,
        replay_engine: ReplayEngineBase,
        event_ids: set[str],
        *,
        name: str = "SubsetAttributionEngine",
    ) -> None:
        self.replay_engine = replay_engine
        self.event_ids = set(event_ids)
        self.name = name

    def score(self, trace: RunTrace) -> AttributionReport:
        t0 = time.perf_counter()
        y_f = self.replay_engine.factual_reward(trace)
        scores: list[CommunicationResponsibility] = []
        cost_total = CostBreakdown()
        for eid in trace.dag.topological_order():
            if eid not in self.event_ids:
                continue
            ev = trace.dag.events[eid]
            intervention = SoftIntervention(
                event_id=eid,
                use_channel_null=True,
                nulls=self.replay_engine.nulls,
                tag=self.name,
            )
            result = self.replay_engine.replay(trace, intervention)
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
                "scored_event_ids": sorted(self.event_ids),
                "cost_breakdown": cost_total.model_dump(mode="json"),
            },
        )
