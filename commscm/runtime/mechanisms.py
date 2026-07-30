"""Deterministic structural mechanisms for exact descendant replay."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from commscm.schema.events import Channel, CommunicationEvent, EventDAG

# mechanism(event, parent_messages_by_id) -> new message string
MechanismFn = Callable[[CommunicationEvent, dict[str, str]], str]


def descendants_of(dag: EventDAG, root_id: str) -> set[str]:
    """All nodes reachable from root_id via directed edges (excluding root)."""
    if root_id not in dag.events:
        raise KeyError(root_id)
    found: set[str] = set()
    stack = list(dag.children(root_id))
    while stack:
        nid = stack.pop()
        if nid in found:
            continue
        found.add(nid)
        stack.extend(dag.children(nid))
    return found


def default_passthrough_mechanism(
    event: CommunicationEvent, parent_msgs: dict[str, str]
) -> str:
    """
    Deterministic descendant update: re-derive message from parents.

    Keeps channel-specific envelope so null parents propagate visibly.
    """
    if not event.parents:
        return event.message
    joined = " | ".join(f"{pid}={parent_msgs[pid]}" for pid in event.parents)
    if event.channel == Channel.TEXT:
        return f"[DERIVED text from {joined}]"
    if event.channel == Channel.TOOL:
        return f'{{"tool":"derived","from":"{joined}"}}'
    if event.channel == Channel.MEMORY:
        return f'{{"op":"derived","from":"{joined}"}}'
    if event.channel == Channel.RETRIEVAL:
        return f'{{"docs":["derived:{joined}"]}}'
    return f"[DERIVED {event.channel.value} from {joined}]"


class MechanismRegistry:
    """Optional per-event mechanisms; missing entries use default_passthrough."""

    def __init__(self, mapping: dict[str, MechanismFn] | None = None) -> None:
        self._mapping = dict(mapping or {})

    def get(self, event_id: str) -> MechanismFn:
        return self._mapping.get(event_id, default_passthrough_mechanism)

    def has(self, event_id: str) -> bool:
        return event_id in self._mapping

    def register(self, event_id: str, fn: MechanismFn) -> None:
        self._mapping[event_id] = fn
