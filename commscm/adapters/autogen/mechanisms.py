"""
Sticky mechanisms for AutoGen-extracted DAGs (adapter-local).

Same pattern as LangGraph sticky registry — preserves recorded payloads under
rematerialization so soft-null CR works on live-shaped traces. Not a Part I/II change.
"""

from __future__ import annotations

from commscm.adapters.autogen.extract import autogen_reward_outcome
from commscm.runtime.mechanisms import MechanismRegistry
from commscm.schema.events import EventDAG
from commscm.traces.langgraph_mechanisms import make_langgraph_sticky_registry


def make_autogen_sticky_registry(dag: EventDAG) -> MechanismRegistry:
    """Reuse sticky factory; DAG shape is isomorphic to LangGraph Part IV."""
    return make_langgraph_sticky_registry(dag)


__all__ = ["make_autogen_sticky_registry", "autogen_reward_outcome"]
