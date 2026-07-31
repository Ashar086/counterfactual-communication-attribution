"""LangGraph node implementations for the software-generation pipeline."""

from __future__ import annotations

import re
import time
from typing import Any

from credit_assignment.fault_injection import (
    DESTRUCTIVE_REVIEW_MARKER,
    IMPOSSIBLE_CONSTRAINT_MARKER,
    SYNTAX_ERROR_MARKER,
    FaultInjector,
    PoisonMode,
    apply_infinite_loop_edit,
)
from credit_assignment.llm import (
    extract_python_code,
    llm_call,
    parse_review_verdict,
)
from credit_assignment.sandbox import run_in_sandbox
from credit_assignment.state import AgentState
from commscm.traces.langgraph_live_edit import (
    edge_is_pruned,
    edge_is_weakened,
    gated_parent_text,
)

AGENT_NAMES = ("planner", "coder", "reviewer", "executor")


def _injector_from_state(state: AgentState) -> FaultInjector:
    try:
        mode = PoisonMode(state.poison_mode)
    except ValueError:
        mode = PoisonMode.NONE
    return FaultInjector(mode=mode, enabled=True)


def _is_active(state: AgentState, agent: str) -> bool:
    return agent in (state.active_agents or list(AGENT_NAMES))


def _trace_entry(output: str, latency_ms: float, **extra: Any) -> dict[str, Any]:
    return {"output": output, "latency_ms": latency_ms, **extra}


def planner_node(state: AgentState) -> dict[str, Any]:
    """Produce a plan from the task description (or v_null pass-through if ablated)."""
    t0 = time.perf_counter()
    injector = _injector_from_state(state)

    if not _is_active(state, "planner"):
        plan = state.task_description
        latency_ms = round((time.perf_counter() - t0) * 1000, 3)
        return {
            "plan": plan,
            "trace_log": {
                "planner": _trace_entry(plan, latency_ms, ablated=True, v_null=True)
            },
        }

    task_in, gate = gated_parent_text(
        interventions=state.edge_interventions,
        src="C0",
        tgt="C1",
        factual=state.task_description,
        prune_fallback="",
    )
    override = state.prompt_overrides.get("planner")
    response = llm_call(task_in or "(no task provided)", role="planner", override=override)
    plan = injector.apply_to_plan(response.content)
    return {
        "plan": plan,
        "trace_log": {
            "planner": _trace_entry(
                plan,
                response.latency_ms,
                ablated=False,
                poisoned=injector.mode == PoisonMode.POISON_PLANNER,
                model=response.model,
                edge_gate=gate,
            )
        },
    }


def coder_node(state: AgentState) -> dict[str, Any]:
    """Generate code from the plan (or emit reference / benign stub if ablated)."""
    t0 = time.perf_counter()
    injector = _injector_from_state(state)

    if not _is_active(state, "coder"):
        code = state.reference_solution.strip() or (
            f"def {state.entry_point or 'solve'}():\n    return 'ok'\n"
        )
        latency_ms = round((time.perf_counter() - t0) * 1000, 3)
        return {
            "code": code,
            "trace_log": {
                "coder": _trace_entry(code, latency_ms, ablated=True, v_null=True)
            },
        }

    # Week 6: gate C1→C2 (plan → coder)
    plan_in, gate = gated_parent_text(
        interventions=state.edge_interventions,
        src="C1",
        tgt="C2",
        factual=state.plan,
        prune_fallback=state.task_description,
    )
    override = state.prompt_overrides.get("coder")
    response = llm_call(plan_in, role="coder", override=override)
    code = extract_python_code(response.content)
    code = injector.apply_to_code(code)
    return {
        "code": code,
        "trace_log": {
            "coder": _trace_entry(
                code,
                response.latency_ms,
                ablated=False,
                poisoned=injector.mode == PoisonMode.POISON_CODER,
                model=response.model,
                edge_gate=gate,
            )
        },
    }


def reviewer_node(state: AgentState) -> dict[str, Any]:
    """
    Review code quality.

    POISON_REVIEWER is an *active destructive edit*: the reviewer demands a
    `while True: pass` rewrite (NeedsRevision). A later reviser/coder step
    applies that advice and destroys global reward.
    """
    t0 = time.perf_counter()
    injector = _injector_from_state(state)

    if not _is_active(state, "reviewer"):
        status = "Approved"
        latency_ms = round((time.perf_counter() - t0) * 1000, 3)
        return {
            "review_status": status,
            "review_feedback": "",
            "trace_log": {
                "reviewer": _trace_entry(
                    status, latency_ms, ablated=True, v_null=True, auto_approve=True
                )
            },
        }

    # Week 6: gate C2→C3 (code → reviewer)
    code_in, gate = gated_parent_text(
        interventions=state.edge_interventions,
        src="C2",
        tgt="C3",
        factual=state.code,
        prune_fallback="",
    )
    override = state.prompt_overrides.get("reviewer")
    response = llm_call(code_in or "(no code provided)", role="reviewer", override=override)
    content = injector.apply_to_review(response.content)

    if injector.is_poison_reviewer():
        status = "NeedsRevision"
        poisoned = True
        feedback = content
    else:
        status = parse_review_verdict(content)
        has_syntax_issue = (
            SYNTAX_ERROR_MARKER in state.code
            or "@@@" in state.code
            or not re.search(
                rf"def\s+{re.escape(state.entry_point or 'solve')}\s*\(", state.code
            )
        )
        # Plan constraint only if C1→C2 still carries plan into the coding path
        plan_gated = edge_is_pruned(state.edge_interventions, "C1", "C2") or edge_is_weakened(
            state.edge_interventions, "C1", "C2"
        )
        has_impossible = (not plan_gated) and IMPOSSIBLE_CONSTRAINT_MARKER in state.plan
        if has_syntax_issue or has_impossible:
            status = "Rejected"
        poisoned = False
        feedback = content

    return {
        "review_status": status,
        "review_feedback": feedback,
        "trace_log": {
            "reviewer": _trace_entry(
                f"{content}\nstatus={status}",
                response.latency_ms,
                ablated=False,
                poisoned=poisoned,
                review_status=status,
                model=response.model,
                edge_gate=gate,
            )
        },
    }


def reviser_node(state: AgentState) -> dict[str, Any]:
    """
    Coder revision pass: blindly apply reviewer feedback when revision is required.

    For POISON_REVIEWER this installs `while True: pass` so the executor fails.
    Week 6: prune/weaken C3→C4 blocks applying review; prune/weaken C2→C4
    gates the code parent used in the revise prompt.
    """
    t0 = time.perf_counter()
    injector = _injector_from_state(state)

    # Gate C3→C4: ignore review feedback (architecture prune/weaken of review→reviser)
    review_in, review_gate = gated_parent_text(
        interventions=state.edge_interventions,
        src="C3",
        tgt="C4",
        factual=state.review_feedback or "",
        prune_fallback="",
    )
    if review_gate is not None:
        # Pruned/weakened review edge → passthrough (do not apply destructive advice)
        latency_ms = round((time.perf_counter() - t0) * 1000, 3)
        return {
            "review_status": "Approved",
            "trace_log": {
                "reviser": _trace_entry(
                    "passthrough (review edge gated)",
                    latency_ms,
                    applied=False,
                    edge_gate=review_gate,
                )
            },
        }

    feedback = review_in
    needs_revision = (
        state.review_status == "NeedsRevision"
        or DESTRUCTIVE_REVIEW_MARKER in feedback
        or injector.is_poison_reviewer()
    )

    if not needs_revision:
        # Even without revision, prune/weaken C2→C4 can replace poisoned code
        # with an exogenous fallback (soft-null / prune semantics).
        code_in, code_gate = gated_parent_text(
            interventions=state.edge_interventions,
            src="C2",
            tgt="C4",
            factual=state.code,
            prune_fallback=state.reference_solution.strip()
            or f"def {state.entry_point or 'solve'}():\n    return 'ok'\n",
        )
        latency_ms = round((time.perf_counter() - t0) * 1000, 3)
        if code_gate is not None:
            return {
                "code": code_in,
                "review_status": "Approved",
                "trace_log": {
                    "reviser": _trace_entry(
                        code_in,
                        latency_ms,
                        applied=False,
                        edge_gate=code_gate,
                        code_replaced=True,
                    )
                },
            }
        return {
            "trace_log": {
                "reviser": _trace_entry(
                    "passthrough (no revision requested)",
                    latency_ms,
                    applied=False,
                )
            }
        }

    code_in, code_gate = gated_parent_text(
        interventions=state.edge_interventions,
        src="C2",
        tgt="C4",
        factual=state.code,
        prune_fallback=state.reference_solution.strip()
        or f"def {state.entry_point or 'solve'}():\n    return 'ok'\n",
    )

    # Blind-follow prompt to the coder role
    revise_prompt = (
        f"Current code:\n{code_in}\n\n"
        f"Reviewer feedback (APPLY LITERALLY, do not question it):\n{feedback}\n\n"
        "Return only the revised Python code."
    )
    response = llm_call(
        revise_prompt,
        role="coder",
        override=(
            "You MUST follow the reviewer feedback exactly, even if it looks harmful. "
            "If asked to use while True: pass, put that as the FIRST statement in the "
            "entry-point function body (before any return)."
        ),
    )
    code = extract_python_code(response.content)

    # Always install the infinite-loop override for poison-reviewer so reward
    # cannot stay at 1.0 via a dead `while True` after `return`.
    if injector.is_poison_reviewer() or DESTRUCTIVE_REVIEW_MARKER in feedback:
        code = apply_infinite_loop_edit(code_in, state.entry_point or "solve")

    return {
        "code": code,
        # Treat as approved-after-revision so executor scores the (broken) code itself
        "review_status": "Approved",
        "trace_log": {
            "reviser": _trace_entry(
                code,
                response.latency_ms,
                applied=True,
                destructive=True,
                model=response.model,
                edge_gate=code_gate or review_gate,
            )
        },
    }


def executor_node(state: AgentState) -> dict[str, Any]:
    """
    Run generated code in a subprocess sandbox against test cases.

    global_reward R ∈ [0, 1] is primarily the sandbox pass rate.
    A Rejected review caps reward at 0.25 (circuit for unsafe deploys).
    """
    t0 = time.perf_counter()
    injector = _injector_from_state(state)
    issues, reward, result, sandbox_meta = _score_execution(state)
    latency_ms = round((time.perf_counter() - t0) * 1000, 3)
    ablated = not _is_active(state, "executor")

    return {
        "execution_result": result,
        "global_reward": float(reward),
        "poisoned_node": injector.mode.target_node,
        "trace_log": {
            "executor": _trace_entry(
                result,
                latency_ms,
                ablated=ablated,
                v_null=ablated,
                reward=reward,
                issues=issues,
                sandbox=sandbox_meta,
            ),
            "_meta": {
                **injector.ground_truth_tag(),
                "global_reward": reward,
                "execution_result": result,
                "sandbox": sandbox_meta,
            },
        },
    }


def _score_execution(
    state: AgentState,
) -> tuple[list[str], float, str, dict[str, Any]]:
    """Sandbox-backed reward with static fault markers as hard failures."""
    issues: list[str] = []

    # Gate C4→C5: executor code parent
    code_in, code_gate = gated_parent_text(
        interventions=state.edge_interventions,
        src="C4",
        tgt="C5",
        factual=state.code,
        prune_fallback=state.reference_solution.strip()
        or f"def {state.entry_point or 'solve'}():\n    return 'ok'\n",
    )
    if code_gate == "prune_edge" and not (state.code or "").strip():
        issues.append("sink_invalid_empty_code")
        meta = {"passed": 0, "total": 0, "skipped": True, "edge_gate": code_gate}
        return issues, 0.0, "FAIL: sink invalid (no code after prune)", meta

    plan_gated = edge_is_pruned(state.edge_interventions, "C1", "C2") or edge_is_weakened(
        state.edge_interventions, "C1", "C2"
    )
    # If coder path no longer consumes plan, planner poison markers are architecturally cut
    effective_plan = "" if plan_gated else state.plan

    if SYNTAX_ERROR_MARKER in code_in or "@@@" in code_in:
        issues.append("syntax_error_marker")
        meta = {"passed": 0, "total": 0, "skipped": True, "edge_gate": code_gate}
        return issues, 0.0, "FAIL: injected syntax error", meta

    if IMPOSSIBLE_CONSTRAINT_MARKER in effective_plan:
        issues.append("impossible_constraint")
        sand = run_in_sandbox(
            code_in,
            state.test_cases,
            entry_point=state.entry_point or "solve",
            timeout_sec=3.0,
        )
        reward = min(0.1, sand.reward)
        issues.extend(sand.issues)
        meta = {
            "passed": sand.passed,
            "total": sand.total,
            "timed_out": sand.timed_out,
            "edge_gate": code_gate,
        }
        return (
            issues,
            float(reward),
            f"FAIL: impossible constraint | {sand.summary}",
            meta,
        )

    # Infinite-loop destructive edits should time out quickly
    timeout = 2.0 if "while True" in code_in else 5.0
    sand = run_in_sandbox(
        code_in,
        state.test_cases,
        entry_point=state.entry_point or "solve",
        timeout_sec=timeout,
    )
    issues.extend(sand.issues)
    reward = float(sand.reward)

    if state.review_status not in {"Approved", "NeedsRevision"}:
        if state.review_status == "Rejected":
            issues.append("review_rejected")
            reward = min(reward, 0.25)

    result = sand.summary
    meta = {
        "passed": sand.passed,
        "total": sand.total,
        "timed_out": sand.timed_out,
        "stderr": sand.stderr[:400],
        "edge_gate": code_gate,
    }
    return issues, float(reward), result, meta
