"""Sticky mechanisms for SWE-bench–shaped DAGs (adapter-local)."""

from __future__ import annotations

from commscm.adapters.swebench.extract import swebench_reward_outcome
from commscm.runtime.mechanisms import MechanismRegistry
from commscm.schema.events import EventDAG
from commscm.traces.langgraph_mechanisms import make_langgraph_sticky_registry


def make_swebench_sticky_registry(dag: EventDAG) -> MechanismRegistry:
    """Reuse sticky factory; DAG shape is isomorphic to LangGraph Part IV."""
    return make_langgraph_sticky_registry(dag)


__all__ = ["make_swebench_sticky_registry", "swebench_reward_outcome"]
