"""Typed soft interventions — null-input, never literal event deletion."""

from __future__ import annotations

from copy import deepcopy
from typing import Callable

from pydantic import BaseModel, Field

from commscm.schema.events import Channel, CommunicationEvent, EventDAG, RunTrace


class NullTemplates(BaseModel):
    """
    Channel-specific baseline messages m^0 used in soft interventions.

    do(m_χ = m^0_χ) replaces factual content with a typed null / pass-through.
    """

    text: str = "[NULL_TEXT] pass-through: ignore prior instructions from this event."
    tool: str = '{"tool":"null","args":{},"status":"skipped"}'
    memory: str = '{"op":"noop","key":null,"value":null}'
    retrieval: str = '{"docs":[],"note":"null_retrieval"}'

    model_config = {"extra": "forbid"}

    def for_channel(self, channel: Channel) -> str:
        return {
            Channel.TEXT: self.text,
            Channel.TOOL: self.tool,
            Channel.MEMORY: self.memory,
            Channel.RETRIEVAL: self.retrieval,
        }[channel]


class SoftIntervention(BaseModel):
    """
    Soft intervention on one communication event's message.

    Semantics: do(m_k = m') while keeping event identity, timing, and edges.
    This replaces the rejected do(C_k = ∅) deletion operator.
    """

    event_id: str
    new_message: str | None = None
    use_channel_null: bool = True
    nulls: NullTemplates = Field(default_factory=NullTemplates)
    tag: str = "soft_null"

    model_config = {"extra": "forbid"}


def apply_soft_intervention(dag: EventDAG, intervention: SoftIntervention) -> EventDAG:
    """Return a copy of `dag` with event message replaced (identity preserved)."""
    if intervention.event_id not in dag.events:
        raise KeyError(f"unknown event_id: {intervention.event_id}")

    new_dag = EventDAG(events={})
    for eid in dag.topological_order():
        event = dag.events[eid]
        if eid != intervention.event_id:
            new_dag.add(event.model_copy(deep=True))
            continue
        if intervention.new_message is not None:
            msg = intervention.new_message
        elif intervention.use_channel_null:
            msg = intervention.nulls.for_channel(event.channel)
        else:
            raise ValueError("new_message required when use_channel_null=False")
        meta = deepcopy(event.meta)
        meta["intervention"] = {
            "tag": intervention.tag,
            "original_message_preview": event.message[:200],
            "channel": event.channel.value,
        }
        new_dag.add(
            CommunicationEvent(
                event_id=event.event_id,
                sender=event.sender,
                receiver=event.receiver,
                channel=event.channel,
                message=msg,
                time_index=event.time_index,
                parents=list(event.parents),
                meta=meta,
            )
        )
    return new_dag


def apply_soft_intervention_to_trace(
    trace: RunTrace,
    intervention: SoftIntervention,
) -> RunTrace:
    """Structural copy of a trace under a soft intervention (outcome left unset/zero)."""
    new_dag = apply_soft_intervention(trace.dag, intervention)
    return trace.model_copy(
        update={
            "dag": new_dag,
            "extra": {
                **trace.extra,
                "intervened": True,
                "intervention_event_id": intervention.event_id,
                "intervention_tag": intervention.tag,
            },
        },
        deep=True,
    )


# Optional hook type for runtime replay engines (Week 2+)
ReplayFn = Callable[[RunTrace, SoftIntervention], float]
