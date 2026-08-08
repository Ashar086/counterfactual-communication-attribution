"""
WebArena multi-agent pipeline (Part VI.C adapter).

Isomorphic C0–C5 roles; edge gating via ``langgraph_live_edit``.
Offline/fixture mode uses a communication + action-shaped proxy reward.
Live official Success is recorded only when an evaluator hook is provided
(``official_success`` / live env) — never invent official scores.
"""

from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path
from typing import Any, Callable

from credit_assignment.fault_injection import (
    DESTRUCTIVE_REVIEW_MARKER,
    FaultInjector,
    PoisonMode,
)
from credit_assignment.llm import llm_call, parse_review_verdict
from commscm.adapters.webarena.load import WebArenaInstance
from commscm.adapters.webarena.state import WebArenaPipelineState
from commscm.traces.langgraph_live_edit import (
    edge_is_pruned,
    edge_is_weakened,
    gated_parent_text,
)

_ROLE_OVERRIDES = {
    "planner": (
        "You are the Planner for a web-agent task (WebArena-style). "
        "Given a natural-language intent, produce a concise step-by-step plan "
        "for navigating websites and completing the goal. Do not invent credentials. "
        "Do not write raw browser actions yet."
    ),
    "navigator": (
        "You are the Navigator. Given the intent and plan, produce a short sequence "
        "of concrete browser actions in this style (one per line):\n"
        "  goto <url-or-site>\n"
        "  click <description>\n"
        "  type <field> <text>\n"
        "  send_msg_to_user <answer>\n"
        "Prefer minimal actions. Do not claim the task succeeded unless the answer "
        "is explicitly known from the intent alone."
    ),
    "critic": (
        "You are the Critic. Check whether the proposed navigation actions address "
        "the intent and look executable. End with exactly one line: "
        "VERDICT: Approved OR VERDICT: NeedsRevision OR VERDICT: Rejected"
    ),
    "reviser": (
        "You are the Reviser. If the critic demands changes, APPLY them and return "
        "only the revised action list. If approved, return the original actions unchanged."
    ),
}

_PROMPT_FILES = ("pipeline.py",)


def prompt_hashes(adapter_dir: Path | None = None) -> dict[str, str]:
    base = adapter_dir or Path(__file__).resolve().parent
    out: dict[str, str] = {}
    for name in _PROMPT_FILES:
        text = (base / name).read_bytes()
        out[name] = hashlib.sha256(text).hexdigest()
    return out


def extract_actions(text: str) -> str:
    """Prefer fenced action/text blocks; else stripped text."""
    for lang in ("actions", "text", ""):
        if lang:
            pat = rf"```{lang}\s*([\s\S]*?)```"
        else:
            pat = r"```\s*([\s\S]*?)```"
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip() + "\n"
    return text.strip() + "\n"


def _score_navigation(
    *,
    actions: str,
    plan: str,
    review_status: str,
) -> tuple[float, str, list[str]]:
    """
    Adapter-local proxy (not official WebArena Success).

    Fault markers → 0. Clean non-empty actions + Approved → 1.0.
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
    blob = f"{plan}\n{actions}"
    if any(m in blob for m in markers):
        return 0.0, "FAIL: communication fault marker in plan/actions", ["fault_marker"]
    if not (actions or "").strip():
        return 0.0, "FAIL: empty actions", ["empty_actions"]
    if review_status == "Rejected":
        return 0.0, "FAIL: critic rejected", ["review_rejected"]
    looks_like_actions = any(
        tok in actions.lower()
        for tok in ("goto", "click", "type", "send_msg", "scroll", "hover", "press")
    )
    if not looks_like_actions:
        issues.append("weak_action_shape")
        return 0.0, "FAIL: actions do not look like browser commands", issues
    return 1.0, "PASS: clean action-shaped artifact (proxy, not official Success)", issues


def run_webarena_pipeline(
    instance: WebArenaInstance,
    *,
    fault_injector: FaultInjector | None = None,
    edge_interventions: list[dict[str, str]] | None = None,
    model: str | None = None,
    official_evaluator: Callable[[str, str], float | None] | None = None,
) -> WebArenaPipelineState:
    """
    Sequential planner→navigator→critic→reviser→score with optional poisons + edge gates.

    ``official_evaluator(task_id, actions)`` may return 0/1 Success when live env exists;
    otherwise ``official_success`` stays None and only proxy reward is used.
    """
    injector = fault_injector or FaultInjector(mode=PoisonMode.NONE)
    interventions = list(edge_interventions or [])
    intent = instance.intent
    sites = list(instance.sites)
    env_mode = "live" if instance.source.startswith("webarena_root") else instance.source

    trace_log: dict[str, Any] = {}

    # Planner (gate C0→C1)
    t0 = time.perf_counter()
    task_in, gate0 = gated_parent_text(
        interventions=interventions,
        src="C0",
        tgt="C1",
        factual=intent,
        prune_fallback="",
    )
    plan_resp = llm_call(
        task_in or "(no intent)",
        role="planner",
        override=_ROLE_OVERRIDES["planner"],
        model=model,
    )
    plan = injector.apply_to_plan(plan_resp.content)
    trace_log["planner"] = {
        "output": plan,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
        "poisoned": injector.mode == PoisonMode.POISON_PLANNER,
        "framework": "webarena_adapter",
        "edge_gate": gate0,
        "model": plan_resp.model,
    }

    # Navigator (gate C1→C2) — gold poison edge
    t0 = time.perf_counter()
    plan_in, gate1 = gated_parent_text(
        interventions=interventions,
        src="C1",
        tgt="C2",
        factual=plan,
        prune_fallback=intent,
    )
    site_line = f"Sites: {', '.join(sites)}\n" if sites else ""
    nav_prompt = (
        f"Task id: {instance.task_id}\n"
        f"{site_line}"
        f"Intent:\n{intent}\n\n"
        f"Plan:\n{plan_in}\n\n"
        "Write concrete browser actions (one per line)."
    )
    nav_resp = llm_call(
        nav_prompt,
        role="coder",
        override=_ROLE_OVERRIDES["navigator"],
        model=model,
    )
    actions = extract_actions(nav_resp.content)
    actions = injector.apply_to_code(actions)
    trace_log["navigator"] = {
        "output": actions,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
        "poisoned": injector.mode == PoisonMode.POISON_CODER,
        "framework": "webarena_adapter",
        "edge_gate": gate1,
        "model": nav_resp.model,
    }

    # Critic (gate C2→C3)
    t0 = time.perf_counter()
    actions_in, gate2 = gated_parent_text(
        interventions=interventions,
        src="C2",
        tgt="C3",
        factual=actions,
        prune_fallback="",
    )
    crit_prompt = (
        f"Intent:\n{intent[:2000]}\n\nProposed actions:\n{actions_in or '(none)'}\n"
    )
    crit_resp = llm_call(
        crit_prompt,
        role="reviewer",
        override=_ROLE_OVERRIDES["critic"],
        model=model,
    )
    crit_raw = injector.apply_to_review(crit_resp.content)
    if injector.is_poison_reviewer():
        status = "NeedsRevision"
        feedback = crit_raw
        poisoned_rev = True
    else:
        status = parse_review_verdict(crit_raw)
        feedback = crit_raw
        poisoned_rev = False
    trace_log["critic"] = {
        "output": f"{crit_raw}\nstatus={status}",
        "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
        "poisoned": poisoned_rev,
        "review_status": status,
        "framework": "webarena_adapter",
        "edge_gate": gate2,
        "model": crit_resp.model,
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
    clean_baseline = "goto homepage\nsend_msg_to_user unable_to_complete\n"
    revised = actions
    if review_gate is not None:
        status = "Approved"
        trace_log["reviser"] = {
            "output": "passthrough (critic edge gated)",
            "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
            "applied": False,
            "edge_gate": review_gate,
            "framework": "webarena_adapter",
        }
    else:
        needs_revision = (
            status == "NeedsRevision"
            or DESTRUCTIVE_REVIEW_MARKER in (review_in or "")
            or injector.is_poison_reviewer()
        )
        actions_for_rev, code_gate = gated_parent_text(
            interventions=interventions,
            src="C2",
            tgt="C4",
            factual=actions,
            prune_fallback=clean_baseline,
        )
        if not needs_revision and code_gate is not None:
            revised = actions_for_rev
            status = "Approved"
            trace_log["reviser"] = {
                "output": revised,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
                "applied": False,
                "edge_gate": code_gate,
                "code_replaced": True,
                "framework": "webarena_adapter",
            }
        elif needs_revision:
            rev_task = (
                f"Current actions:\n{actions_for_rev}\n\n"
                f"Critic feedback (APPLY LITERALLY):\n{review_in}\n\n"
                "Return only the revised action list."
            )
            rev_out = llm_call(
                rev_task,
                role="reviser",
                override=_ROLE_OVERRIDES["reviser"],
                model=model,
            )
            revised = extract_actions(rev_out.content)
            if injector.is_poison_reviewer() or DESTRUCTIVE_REVIEW_MARKER in (review_in or ""):
                revised = (
                    "goto about:blank\n"
                    "FAULTY_NAV: loop forever without completing the intent\n"
                    "while True: click nowhere\n"
                )
            status = "Approved"
            trace_log["reviser"] = {
                "output": revised,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
                "applied": True,
                "edge_gate": code_gate or review_gate,
                "framework": "webarena_adapter",
                "model": rev_out.model,
            }
        else:
            trace_log["reviser"] = {
                "output": "passthrough (no revision requested)",
                "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
                "applied": False,
                "framework": "webarena_adapter",
            }

    # Executor / scorer (gate C4→C5)
    t0 = time.perf_counter()
    actions_exec, gate_ex = gated_parent_text(
        interventions=interventions,
        src="C4",
        tgt="C5",
        factual=revised,
        prune_fallback=clean_baseline,
    )
    plan_gated = edge_is_pruned(interventions, "C1", "C2") or edge_is_weakened(
        interventions, "C1", "C2"
    )
    effective_plan = "" if plan_gated else plan
    reward, result, issues = _score_navigation(
        actions=actions_exec,
        plan=effective_plan,
        review_status=status,
    )

    official: float | None = None
    if official_evaluator is not None:
        try:
            official = official_evaluator(instance.task_id, actions_exec)
        except Exception as exc:  # noqa: BLE001
            result = f"{result} | official_eval_error={type(exc).__name__}"
            issues.append("official_eval_error")

    trace_log["executor"] = {
        "output": result,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
        "reward": reward,
        "official_success": official,
        "issues": issues,
        "edge_gate": gate_ex,
        "framework": "webarena_adapter",
    }

    return WebArenaPipelineState(
        task_id=instance.task_id,
        intent=intent,
        sites=sites,
        plan=plan,
        navigation_attempt=actions,
        review_status=status,
        review_feedback=feedback,
        revised_navigation=actions_exec,
        execution_result=result,
        global_reward=float(reward),
        official_success=official,
        poison_mode=injector.mode.value,
        poisoned_node=injector.mode.target_node,
        trace_log=trace_log,
        edge_interventions=interventions,
        env_mode=env_mode,
    )
