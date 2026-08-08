"""
Sequential AutoGen AgentChat pipeline (Part V adapter).

Roles mirror LangGraph Part IV for Stage-3 invariance comparison.
All framework wiring stays here — not in Parts I–III.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from typing import Any

from credit_assignment.fault_injection import (
    DESTRUCTIVE_REVIEW_MARKER,
    FaultInjector,
    PoisonMode,
    apply_infinite_loop_edit,
)
from credit_assignment.llm import extract_python_code, parse_review_verdict
from credit_assignment.sandbox import run_in_sandbox
from commscm.adapters.autogen.state import AutoGenPipelineState
from commscm.traces.langgraph_live_edit import (
    edge_is_pruned,
    edge_is_weakened,
    gated_parent_text,
)

_SYSTEM = {
    "planner": (
        "You are the Planner in a software-generation pipeline. "
        "Given a task, produce a concise step-by-step plan for implementing a Python "
        "function. Do not write the full implementation."
    ),
    "coder": (
        "You are the Coder. Implement the plan as valid Python code only. "
        "Prefer a single fenced ```python``` block with the required entry-point."
    ),
    "reviewer": (
        "You are the Reviewer. Inspect code for syntax errors and missing entry points. "
        "End with exactly one line: VERDICT: Approved OR VERDICT: NeedsRevision OR VERDICT: Rejected"
    ),
    "reviser": (
        "You are the Reviser. If the reviewer demands changes, APPLY them literally "
        "and return only revised Python code. If approved, return the original code unchanged."
    ),
}


def _last_text(result: Any) -> str:
    msgs = getattr(result, "messages", None) or []
    for m in reversed(list(msgs)):
        content = getattr(m, "content", None)
        if content is None and isinstance(m, dict):
            content = m.get("content")
        if content:
            return str(content)
    return ""


def _msg_dicts(result: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in getattr(result, "messages", None) or []:
        out.append(
            {
                "source": getattr(m, "source", None) or getattr(m, "sender", None),
                "type": type(m).__name__,
                "content": str(getattr(m, "content", "") or "")[:4000],
            }
        )
    return out


def _score_execution(
    *,
    code: str,
    plan: str,
    review_status: str,
    entry_point: str,
    test_cases: list[dict[str, Any]],
) -> tuple[float, str, list[str]]:
    from credit_assignment.fault_injection import (
        IMPOSSIBLE_CONSTRAINT_MARKER,
        SYNTAX_ERROR_MARKER,
    )

    issues: list[str] = []
    if SYNTAX_ERROR_MARKER in code or "@@@" in code:
        return 0.0, "FAIL: injected syntax error", ["syntax_error_marker"]
    if IMPOSSIBLE_CONSTRAINT_MARKER in plan:
        sand = run_in_sandbox(code, test_cases, entry_point=entry_point, timeout_sec=3.0)
        reward = min(0.1, sand.reward)
        return float(reward), f"FAIL: impossible constraint | {sand.summary}", ["impossible_constraint"]
    timeout = 2.0 if "while True" in code else 5.0
    sand = run_in_sandbox(code, test_cases, entry_point=entry_point, timeout_sec=timeout)
    reward = float(sand.reward)
    if review_status == "Rejected":
        reward = min(reward, 0.25)
        issues.append("review_rejected")
    return reward, sand.summary, issues


async def _run_async(
    task_description: str,
    *,
    fault_injector: FaultInjector | None = None,
    entry_point: str = "solve",
    test_cases: list[dict[str, Any]] | None = None,
    reference_solution: str = "",
    model: str | None = None,
    edge_interventions: list[dict[str, str]] | None = None,
) -> AutoGenPipelineState:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_ext.models.openai import OpenAIChatCompletionClient

    injector = fault_injector or FaultInjector(mode=PoisonMode.NONE)
    test_cases = test_cases or []
    interventions = list(edge_interventions or [])
    model_name = model or os.getenv("OPENAI_BASE_MODEL", "gpt-4o-mini")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY required for AutoGen live pipeline")

    client = OpenAIChatCompletionClient(model=model_name, api_key=api_key)
    agents = {
        role: AssistantAgent(role, model_client=client, system_message=sys)
        for role, sys in _SYSTEM.items()
    }

    trace_log: dict[str, Any] = {}
    all_msgs: list[dict[str, Any]] = []

    # Planner (gate C0→C1)
    t0 = time.perf_counter()
    task_in, gate0 = gated_parent_text(
        interventions=interventions,
        src="C0",
        tgt="C1",
        factual=task_description,
        prune_fallback="",
    )
    plan_res = await agents["planner"].run(task=task_in or "(no task provided)")
    plan = injector.apply_to_plan(_last_text(plan_res))
    all_msgs.extend(_msg_dicts(plan_res))
    trace_log["planner"] = {
        "output": plan,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
        "poisoned": injector.mode == PoisonMode.POISON_PLANNER,
        "framework": "autogen_agentchat",
        "edge_gate": gate0,
    }

    # Coder (gate C1→C2)
    t0 = time.perf_counter()
    plan_in, gate1 = gated_parent_text(
        interventions=interventions,
        src="C1",
        tgt="C2",
        factual=plan,
        prune_fallback=task_description,
    )
    coder_prompt = (
        f"Task:\n{task_description}\n\nPlan:\n{plan_in}\n\nWrite the Python implementation."
    )
    code_res = await agents["coder"].run(task=coder_prompt)
    code = extract_python_code(_last_text(code_res))
    code = injector.apply_to_code(code)
    all_msgs.extend(_msg_dicts(code_res))
    trace_log["coder"] = {
        "output": code,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
        "poisoned": injector.mode == PoisonMode.POISON_CODER,
        "framework": "autogen_agentchat",
        "edge_gate": gate1,
    }

    # Reviewer (gate C2→C3)
    t0 = time.perf_counter()
    code_in, gate2 = gated_parent_text(
        interventions=interventions,
        src="C2",
        tgt="C3",
        factual=code,
        prune_fallback="",
    )
    rev_prompt = f"Entry point: {entry_point}\n\nCode:\n{code_in or '(no code)'}\n"
    rev_res = await agents["reviewer"].run(task=rev_prompt)
    rev_raw = injector.apply_to_review(_last_text(rev_res))
    if injector.is_poison_reviewer():
        status = "NeedsRevision"
        feedback = rev_raw
        poisoned_rev = True
    else:
        status = parse_review_verdict(rev_raw)
        feedback = rev_raw
        poisoned_rev = False
    all_msgs.extend(_msg_dicts(rev_res))
    trace_log["reviewer"] = {
        "output": f"{rev_raw}\nstatus={status}",
        "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
        "poisoned": poisoned_rev,
        "review_status": status,
        "framework": "autogen_agentchat",
        "edge_gate": gate2,
    }

    # Reviser (gate C3→C4 review; C2→C4 code)
    t0 = time.perf_counter()
    review_in, review_gate = gated_parent_text(
        interventions=interventions,
        src="C3",
        tgt="C4",
        factual=feedback or "",
        prune_fallback="",
    )
    if review_gate is not None:
        status = "Approved"
        applied = False
        trace_log["reviser"] = {
            "output": "passthrough (review edge gated)",
            "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
            "applied": False,
            "edge_gate": review_gate,
            "framework": "autogen_agentchat",
        }
    else:
        needs_revision = (
            status == "NeedsRevision"
            or DESTRUCTIVE_REVIEW_MARKER in (review_in or "")
            or injector.is_poison_reviewer()
        )
        code_for_rev, code_gate = gated_parent_text(
            interventions=interventions,
            src="C2",
            tgt="C4",
            factual=code,
            prune_fallback=reference_solution.strip()
            or f"def {entry_point}():\n    return 'ok'\n",
        )
        if not needs_revision and code_gate is not None:
            code = code_for_rev
            status = "Approved"
            applied = False
            trace_log["reviser"] = {
                "output": code,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
                "applied": False,
                "edge_gate": code_gate,
                "code_replaced": True,
                "framework": "autogen_agentchat",
            }
        elif needs_revision:
            rev_task = (
                f"Current code:\n{code_for_rev}\n\n"
                f"Reviewer feedback (APPLY LITERALLY):\n{review_in}\n\n"
                "Return only the revised Python code."
            )
            rev_out = await agents["reviser"].run(task=rev_task)
            code = extract_python_code(_last_text(rev_out))
            if injector.is_poison_reviewer() or DESTRUCTIVE_REVIEW_MARKER in (review_in or ""):
                code = apply_infinite_loop_edit(code_for_rev, entry_point)
            all_msgs.extend(_msg_dicts(rev_out))
            status = "Approved"
            applied = True
            trace_log["reviser"] = {
                "output": code,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
                "applied": applied,
                "edge_gate": code_gate or review_gate,
                "framework": "autogen_agentchat",
            }
        else:
            applied = False
            trace_log["reviser"] = {
                "output": "passthrough (no revision requested)",
                "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
                "applied": False,
                "framework": "autogen_agentchat",
            }

    # Executor (gate C4→C5)
    t0 = time.perf_counter()
    code_exec, gate_ex = gated_parent_text(
        interventions=interventions,
        src="C4",
        tgt="C5",
        factual=code,
        prune_fallback=reference_solution.strip()
        or f"def {entry_point}():\n    return 'ok'\n",
    )
    plan_gated = edge_is_pruned(interventions, "C1", "C2") or edge_is_weakened(
        interventions, "C1", "C2"
    )
    effective_plan = "" if plan_gated else plan
    reward, result, issues = _score_execution(
        code=code_exec,
        plan=effective_plan,
        review_status=status,
        entry_point=entry_point,
        test_cases=test_cases,
    )
    trace_log["executor"] = {
        "output": result,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
        "reward": reward,
        "issues": issues,
        "edge_gate": gate_ex,
        "framework": "autogen_agentchat",
    }

    await client.close()

    return AutoGenPipelineState(
        task_description=task_description,
        plan=plan,
        code=code_exec,
        review_status=status,
        review_feedback=feedback,
        execution_result=result,
        global_reward=float(reward),
        poison_mode=injector.mode.value,
        poisoned_node=injector.mode.target_node,
        entry_point=entry_point,
        trace_log=trace_log,
        autogen_messages=all_msgs,
        edge_interventions=interventions,
    )


def run_autogen_pipeline(
    task_description: str,
    *,
    fault_injector: FaultInjector | None = None,
    entry_point: str = "solve",
    test_cases: list[dict[str, Any]] | None = None,
    reference_solution: str = "",
    model: str | None = None,
    edge_interventions: list[dict[str, str]] | None = None,
) -> AutoGenPipelineState:
    """Sync entrypoint for experiments (wraps asyncio)."""
    return asyncio.run(
        _run_async(
            task_description,
            fault_injector=fault_injector,
            entry_point=entry_point,
            test_cases=test_cases,
            reference_solution=reference_solution,
            model=model,
            edge_interventions=edge_interventions,
        )
    )
