#!/usr/bin/env python3
"""
NeurIPS 2026 Workshop — Credit Assignment in Compound Agentic Systems

Demo entrypoint:
  1. Clean pipeline trace
  2. Poisoned pipeline trace (ground truth via FaultInjector)
  3. Exact Shapley values over all 24 permutations
  4. Meta-Agent approximation + Precision@1
  5. Shadow Buffer update cycle (commit if shadow strictly improves reward)
"""

from __future__ import annotations

import json
from pprint import pprint

from credit_assignment.fault_injection import FaultInjector, PoisonMode
from credit_assignment.graph import run_pipeline
from credit_assignment.meta_agent import approximate_credit_assignment, evaluate_meta_agent
from credit_assignment.shadow_buffer import ShadowBuffer
from credit_assignment.shapley import blame_ranking, calculate_exact_shapley


DEMO_TASK = (
    "Write a Python function solve() that returns the string 'ok' "
    "with no network I/O and no side effects."
)
DEMO_TESTS = [{"call": "solve()", "expected": "ok"}]
DEMO_REF = "def solve():\n    return 'ok'\n"

SHADOW_TASKS = [
    "Implement solve() returning 'ok' for identity transform.",
    "Implement solve() as a pure function with unit return 'ok'.",
    "Implement solve() that validates empty input and returns 'ok'.",
    "Implement solve() for a no-op pipeline stage returning 'ok'.",
    "Implement solve() that echoes success via return 'ok'.",
]


def _banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def run_clean_trace() -> None:
    _banner("Step 1 — Clean pipeline trace (no poison)")
    state = run_pipeline(
        DEMO_TASK,
        fault_injector=FaultInjector(mode=PoisonMode.NONE),
        test_cases=DEMO_TESTS,
        reference_solution=DEMO_REF,
    )
    print(f"review_status     : {state.review_status}")
    print(f"execution_result  : {state.execution_result}")
    print(f"global_reward     : {state.global_reward}")
    print(f"poisoned_node     : {state.poisoned_node}")
    print("trace_log keys    :", sorted(k for k in state.trace_log if k != "_meta"))
    print("_meta ground truth:", state.trace_log.get("_meta"))


def run_poisoned_trace_and_attribution() -> None:
    _banner("Step 2–4 — Poisoned trace + Shapley + Meta-Agent")
    injector = FaultInjector(mode=PoisonMode.POISON_CODER)
    state = run_pipeline(
        DEMO_TASK,
        fault_injector=injector,
        test_cases=DEMO_TESTS,
        reference_solution=DEMO_REF,
    )

    print(f"poison_mode       : {state.poison_mode}")
    print(f"poisoned_node     : {state.poisoned_node}  <- ground truth")
    print(f"execution_result  : {state.execution_result}")
    print(f"global_reward     : {state.global_reward}")
    print(f"review_status     : {state.review_status}")

    print("\n--- Exact Shapley values (24 permutations) ---")
    shapley = calculate_exact_shapley(state, injector)
    pprint(shapley)
    ranking = blame_ranking(shapley)
    print("Blame ranking (lowest φ first):", ranking)
    print(f"Shapley top-blame candidate  : {ranking[0][0]}")

    print("\n--- Meta-Agent approximation ---")
    meta = approximate_credit_assignment(state)
    print(json.dumps({k: meta[k] for k in ("attribution", "highest_blame", "rationale")}, indent=2))

    evaluation = evaluate_meta_agent(state, meta)
    print("\n--- Precision@1 evaluation ---")
    pprint(evaluation)


def run_shadow_buffer_cycle() -> None:
    _banner("Step 5 — Shadow Buffer circuit breaker")
    buffer = ShadowBuffer(k=5)

    # Base graph currently uses a degraded coder prompt (low reward).
    buffer.committed_prompts["coder"] = "DEGRADED: loose generation without solve()"

    # Meta-Agent proposes a hardened prompt for the failing coder node.
    proposed = "HARDENED: enforce def solve() and strict syntax"
    print(f"Target agent      : coder")
    print(f"Proposed prompt   : {proposed}")
    print(f"Current committed : {buffer.committed_prompts}")

    decision = buffer.simulate_update_cycle(
        target_agent="coder",
        proposed_prompt=proposed,
        tasks=SHADOW_TASKS,
        fault_injector=FaultInjector(mode=PoisonMode.NONE),
    )

    print(f"\nbase_avg_reward   : {decision.base_avg_reward:.4f}")
    print(f"shadow_avg_reward : {decision.shadow_avg_reward:.4f}")
    print(f"committed         : {decision.committed}")
    print(f"log               : {decision.log_message}")
    print("per-trial rewards :")
    for t in decision.trials:
        print(f"  base={t.base_reward:.2f}  shadow={t.shadow_reward:.2f}  | {t.task[:48]}...")

    print(f"\ncommitted_prompts after cycle: {buffer.committed_prompts}")
    print(f"rollback_log entries         : {len(buffer.rollback_log)}")
    print(f"commit_log entries           : {len(buffer.commit_log)}")

    # Second proposal that does not improve → rollback
    print("\n--- Second proposal (should ROLLBACK) ---")
    bad_proposal = "DEGRADED: even worse coder prompt"
    decision2 = buffer.simulate_update_cycle(
        target_agent="coder",
        proposed_prompt=bad_proposal,
        tasks=SHADOW_TASKS,
        fault_injector=FaultInjector(mode=PoisonMode.NONE),
    )
    print(decision2.log_message)
    print(f"rollback_log[-1]: {buffer.rollback_log[-1] if buffer.rollback_log else None}")


def main() -> None:
    run_clean_trace()
    run_poisoned_trace_and_attribution()
    run_shadow_buffer_cycle()
    _banner("Done")


if __name__ == "__main__":
    main()
