"""
SWE-bench Verified–shaped multi-agent pipeline (Part VI adapter).

Uses problem statements from SWE-bench Verified; isomorphic C0–C5 roles;
edge gating via ``langgraph_live_edit`` (same as AutoGen).

Scope: not the official Docker resolve@1 harness — reward is a
communication-fault + patch-shaped proxy (see ``_score_patch``).
"""

from __future__ import annotations

import re
import time
from typing import Any

from credit_assignment.fault_injection import (
    DESTRUCTIVE_REVIEW_MARKER,
    FaultInjector,
    PoisonMode,
    apply_infinite_loop_edit,
)
from credit_assignment.llm import extract_python_code, llm_call, parse_review_verdict
from commscm.adapters.swebench.load import SWEBenchInstance
from commscm.adapters.swebench.state import SWEBenchPipelineState
from commscm.traces.langgraph_live_edit import (
    edge_is_pruned,
    edge_is_weakened,
    gated_parent_text,
)

_ROLE_OVERRIDES = {
    "planner": (
        "You are the Planner for a software-engineering repair attempt. "
        "Given a GitHub issue / bug report (SWE-bench style), produce a concise "
        "step-by-step plan for a minimal patch. Do not write the full patch yet."
    ),
    "coder": (
        "You are the Coder. Produce a minimal unified-diff style patch (or a short "
        "Python snippet that would fix the bug). Prefer a fenced ```diff``` or "
        "```python``` block. Do not invent unrelated files."
    ),
    "reviewer": (
        "You are the Reviewer. Check whether the proposed patch addresses the issue "
        "and looks syntactically coherent. End with exactly one line: "
        "VERDICT: Approved OR VERDICT: NeedsRevision OR VERDICT: Rejected"
    ),
    "reviser": (
        "You are the Reviser. If the reviewer demands changes, APPLY them and return "
        "only the revised patch. If approved, return the original patch unchanged."
    ),
}


def extract_patch(text: str) -> str:
    """Prefer fenced diff/patch/python; else stripped text."""
    for lang in ("diff", "patch", "python", ""):
        if lang:
            pat = rf"```{lang}\s*([\s\S]*?)```"
        else:
            pat = r"```\s*([\s\S]*?)```"
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip() + "\n"
    return text.strip() + "\n"


def _score_patch(
    *,
    patch: str,
    plan: str,
    review_status: str,
) -> tuple[float, str, list[str]]:
    """
    Adapter-local reward proxy (not Docker resolve@1).

    Fault markers → 0. Clean non-empty patch + Approved → 1.0.
    """
    from credit_assignment.fault_injection import (
        IMPOSSIBLE_CONSTRAINT_MARKER,
        INFINITE_LOOP_MARKER,
        SYNTAX_ERROR_MARKER,
    )

    issues: list[str] = []
    markers = (
        SYNTAX_ERROR_MARKER,
        IMPOSSIBLE_CONSTRAINT_MARKER,
        DESTRUCTIVE_REVIEW_MARKER,
        INFINITE_LOOP_MARKER,
        "FAULT_",
        "while True",
        "@@@",
    )
    blob = f"{plan}\n{patch}"
    if any(m in blob for m in markers):
        return 0.0, "FAIL: communication fault marker in plan/patch", ["fault_marker"]
    if not (patch or "").strip():
        return 0.0, "FAIL: empty patch", ["empty_patch"]
    if review_status == "Rejected":
        return 0.0, "FAIL: review rejected", ["review_rejected"]
    # Weak structural signal that the agent produced a patch-shaped artifact
    looks_like_patch = any(
        tok in patch for tok in ("+++", "---", "@@", "def ", "class ", "return ", "diff ")
    )
    if not looks_like_patch:
        issues.append("weak_patch_shape")
        return 0.0, "FAIL: patch does not look like code/diff", issues
    return 1.0, "PASS: clean patch-shaped artifact (proxy, not Docker)", issues


def run_swebench_pipeline(
    instance: SWEBenchInstance,
    *,
    fault_injector: FaultInjector | None = None,
    edge_interventions: list[dict[str, str]] | None = None,
    model: str | None = None,
) -> SWEBenchPipelineState:
    """
    Sequential planner→coder→reviewer→reviser→score with optional poisons + edge gates.
    """
    injector = fault_injector or FaultInjector(mode=PoisonMode.NONE)
    interventions = list(edge_interventions or [])
    problem = instance.problem_statement
    hints = (instance.hints_text or "").strip()
    task_block = problem
    if hints:
        task_block = f"{problem}\n\nHints:\n{hints}"

    trace_log: dict[str, Any] = {}

    # Planner (gate C0→C1)
    t0 = time.perf_counter()
    task_in, gate0 = gated_parent_text(
        interventions=interventions,
        src="C0",
        tgt="C1",
        factual=task_block,
        prune_fallback="",
    )
    plan_resp = llm_call(
        task_in or "(no problem statement)",
        role="planner",
        override=_ROLE_OVERRIDES["planner"],
        model=model,
    )
    plan = injector.apply_to_plan(plan_resp.content)
    trace_log["planner"] = {
        "output": plan,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
        "poisoned": injector.mode == PoisonMode.POISON_PLANNER,
        "framework": "swebench_shaped",
        "edge_gate": gate0,
        "model": plan_resp.model,
    }

    # Coder (gate C1→C2)
    t0 = time.perf_counter()
    plan_in, gate1 = gated_parent_text(
        interventions=interventions,
        src="C1",
        tgt="C2",
        factual=plan,
        prune_fallback=task_block,
    )
    coder_prompt = (
        f"Repository: {instance.repo or 'unknown'}\n"
        f"Instance: {instance.instance_id}\n\n"
        f"Problem:\n{task_block}\n\n"
        f"Plan:\n{plan_in}\n\n"
        "Write a minimal fix as a unified diff or short Python patch."
    )
    code_resp = llm_call(
        coder_prompt,
        role="coder",
        override=_ROLE_OVERRIDES["coder"],
        model=model,
    )
    patch = extract_patch(code_resp.content)
    if not patch.strip():
        patch = extract_python_code(code_resp.content)
    patch = injector.apply_to_code(patch)
    trace_log["coder"] = {
        "output": patch,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
        "poisoned": injector.mode == PoisonMode.POISON_CODER,
        "framework": "swebench_shaped",
        "edge_gate": gate1,
        "model": code_resp.model,
    }

    # Reviewer (gate C2→C3)
    t0 = time.perf_counter()
    patch_in, gate2 = gated_parent_text(
        interventions=interventions,
        src="C2",
        tgt="C3",
        factual=patch,
        prune_fallback="",
    )
    rev_prompt = (
        f"Issue:\n{problem[:2000]}\n\nProposed patch:\n{patch_in or '(no patch)'}\n"
    )
    rev_resp = llm_call(
        rev_prompt,
        role="reviewer",
        override=_ROLE_OVERRIDES["reviewer"],
        model=model,
    )
    rev_raw = injector.apply_to_review(rev_resp.content)
    if injector.is_poison_reviewer():
        status = "NeedsRevision"
        feedback = rev_raw
        poisoned_rev = True
    else:
        status = parse_review_verdict(rev_raw)
        feedback = rev_raw
        poisoned_rev = False
    trace_log["reviewer"] = {
        "output": f"{rev_raw}\nstatus={status}",
        "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
        "poisoned": poisoned_rev,
        "review_status": status,
        "framework": "swebench_shaped",
        "edge_gate": gate2,
        "model": rev_resp.model,
    }

    # Reviser (gate C3→C4 / C2→C4)
    t0 = time.perf_counter()
    review_in, review_gate = gated_parent_text(
        interventions=interventions,
        src="C3",
        tgt="C4",
        factual=feedback or "",
        prune_fallback="",
    )
    # Soft-null replacement for pruned agent payloads (NOT dataset gold_patch —
    # oracle leakage). Analogous to AutoGen ``reference_solution`` baseline.
    clean_baseline = (
        "--- a/fix.py\n+++ b/fix.py\n"
        "@@\n+def apply_patch():\n+    return 'ok'\n"
    )
    if review_gate is not None:
        status = "Approved"
        trace_log["reviser"] = {
            "output": "passthrough (review edge gated)",
            "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
            "applied": False,
            "edge_gate": review_gate,
            "framework": "swebench_shaped",
        }
    else:
        needs_revision = (
            status == "NeedsRevision"
            or DESTRUCTIVE_REVIEW_MARKER in (review_in or "")
            or injector.is_poison_reviewer()
        )
        patch_for_rev, code_gate = gated_parent_text(
            interventions=interventions,
            src="C2",
            tgt="C4",
            factual=patch,
            prune_fallback=clean_baseline,
        )
        if not needs_revision and code_gate is not None:
            patch = patch_for_rev
            status = "Approved"
            trace_log["reviser"] = {
                "output": patch,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
                "applied": False,
                "edge_gate": code_gate,
                "code_replaced": True,
                "framework": "swebench_shaped",
            }
        elif needs_revision:
            rev_task = (
                f"Current patch:\n{patch_for_rev}\n\n"
                f"Reviewer feedback (APPLY LITERALLY):\n{review_in}\n\n"
                "Return only the revised patch."
            )
            rev_out = llm_call(
                rev_task,
                role="reviser",
                override=_ROLE_OVERRIDES["reviser"],
                model=model,
            )
            patch = extract_patch(rev_out.content)
            if injector.is_poison_reviewer() or DESTRUCTIVE_REVIEW_MARKER in (review_in or ""):
                # Preserve poison effect isomorphic to AutoGen (infinite-loop edit)
                patch = apply_infinite_loop_edit(patch_for_rev, "apply_patch")
            status = "Approved"
            trace_log["reviser"] = {
                "output": patch,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
                "applied": True,
                "edge_gate": code_gate or review_gate,
                "framework": "swebench_shaped",
                "model": rev_out.model,
            }
        else:
            trace_log["reviser"] = {
                "output": "passthrough (no revision requested)",
                "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
                "applied": False,
                "framework": "swebench_shaped",
            }

    # Executor / scorer (gate C4→C5)
    t0 = time.perf_counter()
    patch_exec, gate_ex = gated_parent_text(
        interventions=interventions,
        src="C4",
        tgt="C5",
        factual=patch,
        prune_fallback=clean_baseline,
    )
    plan_gated = edge_is_pruned(interventions, "C1", "C2") or edge_is_weakened(
        interventions, "C1", "C2"
    )
    effective_plan = "" if plan_gated else plan
    reward, result, issues = _score_patch(
        patch=patch_exec,
        plan=effective_plan,
        review_status=status,
    )

    trace_log["executor"] = {
        "output": result,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
        "reward": reward,
        "issues": issues,
        "edge_gate": gate_ex,
        "framework": "swebench_shaped",
    }

    return SWEBenchPipelineState(
        instance_id=instance.instance_id,
        problem_statement=problem,
        repo=instance.repo,
        plan=plan,
        patch_attempt=patch_exec,
        review_status=status,
        review_feedback=feedback,
        execution_result=result,
        global_reward=float(reward),
        poison_mode=injector.mode.value,
        poisoned_node=injector.mode.target_node,
        gold_patch=instance.gold_patch,
        fail_to_pass=list(instance.fail_to_pass),
        trace_log=trace_log,
        edge_interventions=interventions,
    )
