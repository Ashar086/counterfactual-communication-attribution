"""
LangGraph sticky mechanisms for recorded traces (Week 5).

Preserves channel-native local injections under parent edits unless a parent
is soft-nulled (then downstream rederives). Used only by the LangGraph adapter;
does not modify core replay engines.
"""

from __future__ import annotations

from credit_assignment.fault_injection import (
    DESTRUCTIVE_REVIEW_MARKER,
    IMPOSSIBLE_CONSTRAINT_MARKER,
    INFINITE_LOOP_MARKER,
    SYNTAX_ERROR_MARKER,
)
from commscm.interventions.soft import NullTemplates
from commscm.runtime.mechanisms import MechanismRegistry, default_passthrough_mechanism
from commscm.schema.events import EventDAG

_MARKERS = (
    IMPOSSIBLE_CONSTRAINT_MARKER,
    SYNTAX_ERROR_MARKER,
    DESTRUCTIVE_REVIEW_MARKER,
    INFINITE_LOOP_MARKER,
)


def _has_marker(msg: str) -> bool:
    return any(m in (msg or "") for m in _MARKERS)


def _is_null_msg(msg: str) -> bool:
    nulls = NullTemplates()
    return msg in {nulls.text, nulls.tool, nulls.memory, nulls.retrieval} or msg.startswith(
        "[NULL_"
    )


def make_langgraph_sticky_registry(factual: EventDAG) -> MechanismRegistry:
    def make_fn(event_id: str):
        def mech(event, parent_msgs: dict[str, str]) -> str:
            factual_ev = factual.events[event_id]
            if not event.parents:
                return factual_ev.message
            parents_changed = any(
                parent_msgs[p] != factual.events[p].message for p in event.parents
            )
            if not parents_changed:
                return factual_ev.message
            # Downstream of a soft-null: rederive unless this node has a *local*
            # channel-native injection (marker not explained by factual parents).
            if any(_is_null_msg(parent_msgs[p]) for p in event.parents):
                local = _has_marker(factual_ev.message) and not any(
                    _has_marker(factual.events[p].message) for p in event.parents
                )
                if local:
                    return factual_ev.message
                return default_passthrough_mechanism(event, parent_msgs)
            # Local injection (marker not present in factual parents): keep recorded.
            local = _has_marker(factual_ev.message) and not any(
                _has_marker(factual.events[p].message) for p in event.parents
            )
            if local:
                return factual_ev.message
            return default_passthrough_mechanism(event, parent_msgs)

        return mech

    mapping = {
        eid: make_fn(eid)
        for eid, ev in factual.events.items()
        if ev.parents
    }
    return MechanismRegistry(mapping)
