"""Typed information-flow events and time-indexed DAG schema."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class Channel(str, Enum):
    """Information-flow channel χ for a communication event."""

    TEXT = "text"
    TOOL = "tool"
    MEMORY = "memory"
    RETRIEVAL = "retrieval"


class CommunicationEvent(BaseModel):
    """
    Atomic unit C_k of CommSCM.

    C_k = (id, sender, receiver, channel, message, time_index, parents, meta)

    Notes
    -----
    - `message` is channel-typed content (text, tool JSON, memory write, retrieval hit).
    - Literal deletion do(C=∅) is forbidden; intervene via soft null-input on `message`.
    - confidence/cost live in `meta`, not as a first-class causal coordinate.
    """

    event_id: str
    sender: str
    receiver: str
    channel: Channel
    message: str
    time_index: int = Field(ge=0)
    parents: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    @field_validator("event_id", "sender", "receiver")
    @classmethod
    def _nonempty(cls, v: str) -> str:
        if not v or not str(v).strip():
            raise ValueError("must be non-empty")
        return str(v).strip()


class EventDAG(BaseModel):
    """Time-indexed DAG over communication events (IF-C-SCM structural skeleton)."""

    events: dict[str, CommunicationEvent] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    def add(self, event: CommunicationEvent) -> None:
        if event.event_id in self.events:
            raise ValueError(f"duplicate event_id: {event.event_id}")
        for p in event.parents:
            if p not in self.events:
                raise ValueError(f"parent {p!r} missing for {event.event_id}")
            if self.events[p].time_index > event.time_index:
                raise ValueError(
                    f"time order violated: parent {p} time={self.events[p].time_index} "
                    f"> event {event.event_id} time={event.time_index}"
                )
        self.events[event.event_id] = event

    def children(self, event_id: str) -> list[str]:
        return [eid for eid, e in self.events.items() if event_id in e.parents]

    def topological_order(self) -> list[str]:
        pending = dict(self.events)
        ordered: list[str] = []
        ready = [eid for eid, e in pending.items() if not e.parents]
        ready.sort(key=lambda i: (pending[i].time_index, i))
        while ready:
            eid = ready.pop(0)
            ordered.append(eid)
            del pending[eid]
            for cid, child in list(pending.items()):
                if all(p not in pending for p in child.parents):
                    if cid not in ready:
                        ready.append(cid)
            ready.sort(key=lambda i: (pending[i].time_index, i))
        if pending:
            raise ValueError(f"cycle or unresolved parents: {sorted(pending)}")
        return ordered

    def subgraph(self, keep_ids: set[str]) -> "EventDAG":
        out = EventDAG()
        for eid in self.topological_order():
            if eid not in keep_ids:
                continue
            e = self.events[eid]
            out.add(
                e.model_copy(
                    update={"parents": [p for p in e.parents if p in keep_ids]}
                )
            )
        return out


class RunOutcome(BaseModel):
    """Terminal outcome Y for a run (task utility in [0, 1] by convention)."""

    reward: float = Field(ge=0.0, le=1.0)
    success: bool = False
    metrics: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class RunTrace(BaseModel):
    """Serializable factual trace for counterfactual attribution."""

    run_id: str
    task_id: str
    architecture_id: str = "default"
    dag: EventDAG
    outcome: RunOutcome
    gold_fault_event_id: str | None = None
    gold_fault_event_ids: list[str] = Field(default_factory=list)
    poison_mode: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _gold_in_dag(self) -> "RunTrace":
        ids = list(self.gold_fault_event_ids)
        if self.gold_fault_event_id and self.gold_fault_event_id not in ids:
            ids = [self.gold_fault_event_id, *ids]
        for gid in ids:
            if gid not in self.dag.events:
                raise ValueError(f"gold fault id {gid!r} not in DAG")
        object.__setattr__(self, "gold_fault_event_ids", ids)
        if ids and not self.gold_fault_event_id:
            object.__setattr__(self, "gold_fault_event_id", ids[0])
        return self
