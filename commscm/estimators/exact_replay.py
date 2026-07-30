"""Exact counterfactual replay under typed soft interventions."""

from __future__ import annotations

import time
from copy import deepcopy
from typing import Callable

from pydantic import BaseModel, Field

from commscm.interventions.soft import NullTemplates, SoftIntervention
from commscm.runtime.mechanisms import MechanismRegistry, descendants_of
from commscm.schema.events import CommunicationEvent, EventDAG, RunOutcome, RunTrace

OutcomeFn = Callable[[EventDAG], float]


class ReplayResult(BaseModel):
    """Result of one exact soft-intervention replay."""

    intervened_event_id: str
    factual_reward: float
    counterfactual_reward: float
    counterfactual_dag: EventDAG
    recomputed_event_ids: list[str] = Field(default_factory=list)
    unchanged_event_ids: list[str] = Field(default_factory=list)
    runtime_ms: float = 0.0

    model_config = {"extra": "forbid"}


class ExactReplayEngine:
    """
    Exact CF replay for small DAGs (≈5–20 events).

    - Soft-intervene message of one event (identity / time / topology preserved).
    - Recompute only that event's descendants via deterministic mechanisms.
    - Non-descendants remain bitwise-identical to the factual messages.
    """

    def __init__(
        self,
        outcome_fn: OutcomeFn,
        mechanisms: MechanismRegistry | None = None,
        nulls: NullTemplates | None = None,
    ) -> None:
        self.outcome_fn = outcome_fn
        self.mechanisms = mechanisms or MechanismRegistry()
        self.nulls = nulls or NullTemplates()

    def factual_reward(self, trace: RunTrace) -> float:
        return float(self.outcome_fn(trace.dag))

    def replay(
        self,
        trace: RunTrace,
        intervention: SoftIntervention,
    ) -> ReplayResult:
        t0 = time.perf_counter()
        dag = trace.dag
        eid = intervention.event_id
        if eid not in dag.events:
            raise KeyError(f"unknown event_id: {eid}")

        factual_y = float(self.outcome_fn(dag))
        desc = descendants_of(dag, eid)
        affected = {eid} | desc

        # Resolve intervened message
        base = dag.events[eid]
        if intervention.new_message is not None:
            new_msg = intervention.new_message
        elif intervention.use_channel_null:
            # Prefer engine nulls; allow intervention override templates
            tmpl = intervention.nulls if intervention.nulls else self.nulls
            new_msg = tmpl.for_channel(base.channel)
        else:
            raise ValueError("new_message required when use_channel_null=False")

        # Build CF DAG in topological order
        cf = EventDAG()
        recomputed: list[str] = []
        unchanged: list[str] = []
        messages: dict[str, str] = {}

        for nid in dag.topological_order():
            factual = dag.events[nid]
            if nid == eid:
                meta = deepcopy(factual.meta)
                meta["intervention"] = {
                    "tag": intervention.tag,
                    "original_message_preview": factual.message[:200],
                    "channel": factual.channel.value,
                }
                msg = new_msg
                recomputed.append(nid)
            elif nid in desc and self.mechanisms.has(nid):
                # Structural descendants with an explicit mechanism are recomputed.
                # Exogenous events keep factual messages unless directly intervened.
                parent_msgs = {p: messages[p] for p in factual.parents}
                mech = self.mechanisms.get(nid)
                msg = mech(factual, parent_msgs)
                meta = deepcopy(factual.meta)
                meta["recomputed"] = True
                recomputed.append(nid)
            else:
                msg = factual.message
                meta = deepcopy(factual.meta)
                unchanged.append(nid)

            messages[nid] = msg
            cf.add(
                CommunicationEvent(
                    event_id=factual.event_id,
                    sender=factual.sender,
                    receiver=factual.receiver,
                    channel=factual.channel,
                    message=msg,
                    time_index=factual.time_index,
                    parents=list(factual.parents),
                    meta=meta,
                )
            )

        # Bitwise check for non-descendants
        for nid in unchanged:
            if cf.events[nid].message != dag.events[nid].message:
                raise RuntimeError(f"non-descendant {nid} message mutated")

        y_cf = float(self.outcome_fn(cf))
        runtime_ms = round((time.perf_counter() - t0) * 1000, 3)
        return ReplayResult(
            intervened_event_id=eid,
            factual_reward=factual_y,
            counterfactual_reward=y_cf,
            counterfactual_dag=cf,
            recomputed_event_ids=recomputed,
            unchanged_event_ids=unchanged,
            runtime_ms=runtime_ms,
        )


def fault_marker_outcome(dag: EventDAG) -> float:
    """Y=0 if any message contains FAULT_; else Y=1. Deterministic."""
    for e in dag.events.values():
        if "FAULT_" in e.message:
            return 0.0
    return 1.0
