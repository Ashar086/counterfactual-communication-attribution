"""Exact Shapley value credit assignment over the 4-agent coalition."""

from __future__ import annotations

import itertools
import math
from typing import Any

from credit_assignment.fault_injection import FaultInjector, PoisonMode
from credit_assignment.graph import run_pipeline
from credit_assignment.nodes import AGENT_NAMES
from credit_assignment.state import AgentState


def _characteristic_value(
    coalition: set[str],
    task_description: str,
    fault_injector: FaultInjector,
    *,
    entry_point: str = "solve",
    test_cases: list[dict[str, Any]] | None = None,
    reference_solution: str = "",
) -> float:
    """
    v(S): global reward when only agents in `coalition` are active.

    Ablated agents use v_null pass-throughs defined in the node implementations:
      - Planner ablated → task_description passed to the coding stage as plan
      - Coder ablated → reference_solution (or benign stub)
      - Reviewer ablated → auto-approve
      - Executor ablated → same sandbox reward model (environment scorer)

    Fault injection only mutates an agent if that agent is active in S
    (poison cannot fire through a pass-through).
    """
    effective = fault_injector
    target = fault_injector.mode.target_node
    if target is not None and target not in coalition:
        effective = FaultInjector(mode=PoisonMode.NONE, enabled=False)

    result = run_pipeline(
        task_description,
        fault_injector=effective,
        active_agents=sorted(coalition),
        entry_point=entry_point,
        test_cases=test_cases,
        reference_solution=reference_solution,
    )
    return float(result.global_reward)


def calculate_exact_shapley(
    trace: AgentState | dict[str, Any],
    fault_injector_state: FaultInjector | dict[str, Any] | PoisonMode | str,
) -> dict[str, float]:
    """
    Exact Shapley values φ_i for V = {planner, coder, reviewer, executor}.

    Iterates all |V|! = 24 permutations:

        φ_i = (1/n!) Σ_π [ v(S_π^i ∪ {i}) − v(S_π^i) ]

    where S_π^i is the set of agents preceding i in permutation π.

    Args:
        trace: Completed pipeline trace (used for task_description + context).
        fault_injector_state: FaultInjector, dict, PoisonMode, or mode string
            matching the ground-truth condition under which the trace was run.

    Returns:
        Mapping agent_name → exact Shapley value (marginal reward contribution).
    """
    if isinstance(trace, AgentState):
        task = trace.task_description
        entry_point = trace.entry_point
        test_cases = list(trace.test_cases)
        reference_solution = trace.reference_solution
    else:
        task = str(trace.get("task_description", ""))
        entry_point = str(trace.get("entry_point", "solve"))
        test_cases = list(trace.get("test_cases") or [])
        reference_solution = str(trace.get("reference_solution") or "")

    if isinstance(fault_injector_state, FaultInjector):
        injector = fault_injector_state
    elif isinstance(fault_injector_state, PoisonMode):
        injector = FaultInjector(mode=fault_injector_state)
    elif isinstance(fault_injector_state, str):
        injector = FaultInjector(mode=PoisonMode(fault_injector_state))
    elif isinstance(fault_injector_state, dict):
        mode_raw = fault_injector_state.get("mode", fault_injector_state.get("poison_mode", "NONE"))
        if isinstance(mode_raw, PoisonMode):
            mode = mode_raw
        else:
            mode = PoisonMode(str(mode_raw))
        injector = FaultInjector(mode=mode, enabled=fault_injector_state.get("enabled", True))
    else:
        raise TypeError(f"Unsupported fault_injector_state type: {type(fault_injector_state)}")

    agents = list(AGENT_NAMES)
    n = len(agents)
    shapley: dict[str, float] = {a: 0.0 for a in agents}

    # Cache v(S) across permutations (2^4 = 16 coalitions)
    value_cache: dict[frozenset[str], float] = {}

    def v(coalition: set[str]) -> float:
        key = frozenset(coalition)
        if key not in value_cache:
            value_cache[key] = _characteristic_value(
                coalition,
                task,
                injector,
                entry_point=entry_point,
                test_cases=test_cases,
                reference_solution=reference_solution,
            )
        return value_cache[key]

    for permutation in itertools.permutations(agents):
        preceding: set[str] = set()
        for agent in permutation:
            before = v(preceding)
            after = v(preceding | {agent})
            shapley[agent] += after - before
            preceding.add(agent)

    for agent in agents:
        shapley[agent] = round(shapley[agent] / float(math.factorial(n)), 6)

    return shapley


def blame_ranking(shapley_values: dict[str, float]) -> list[tuple[str, float]]:
    """
    Rank agents by blame: lowest (most negative) Shapley contribution first.
    Negative φ_i ⇒ agent reduced coalition reward when added ⇒ likely fault source.
    """
    return sorted(shapley_values.items(), key=lambda kv: kv[1])
