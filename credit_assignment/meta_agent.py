"""LLM-based Meta-Agent approximation of credit assignment."""

from __future__ import annotations

import json
from typing import Any

from credit_assignment.llm import (
    llm_call,
    mock_meta_attribution_json,
    parse_meta_attribution_json,
)
from credit_assignment.state import AgentState


def approximate_credit_assignment(
    trace_log: dict[str, Any] | AgentState,
) -> dict[str, Any]:
    """
    Meta-Agent (gpt-4o by default): counterfactual CoT then JSON blame scores.

    Returns:
      {
        "attribution": {"planner": float, ...},
        "highest_blame": str,
        "rationale": str,
        "raw_llm": str,
        "latency_ms": float,
        "model": str,
      }
    """
    if isinstance(trace_log, AgentState):
        log = dict(trace_log.trace_log)
        reward = trace_log.global_reward
        exec_result = trace_log.execution_result
        task = trace_log.task_description
        plan = trace_log.plan
        code = trace_log.code
        review_feedback = trace_log.review_feedback
    else:
        log = dict(trace_log)
        meta = log.get("_meta") or {}
        reward = meta.get("global_reward")
        exec_result = meta.get("execution_result", "")
        task = str(log.get("task_description", ""))
        plan = str((log.get("planner") or {}).get("output", ""))
        code = str((log.get("coder") or {}).get("output", ""))
        review_feedback = str(log.get("review_feedback", ""))

    # Strip ground-truth keys from the prompt copy
    prompt_log = {k: v for k, v in log.items() if k != "_meta"}
    meta_public = {
        "global_reward": reward,
        "execution_result": exec_result,
    }

    prompt = (
        "Perform counterfactual credit assignment for this compound agent run.\n\n"
        "=== ORIGINAL USER TASK ===\n"
        f"{task[:800]}\n\n"
        "=== PLANNER OUTPUT (compare to task in Step 1) ===\n"
        f"{plan[:1200]}\n\n"
        "=== CODER OUTPUT ===\n"
        f"{code[:1200]}\n\n"
        "=== REVIEW FEEDBACK ===\n"
        f"{(review_feedback or str((prompt_log.get('reviewer') or {}).get('output', '')))[:800]}\n\n"
        "=== RUN SUMMARY ===\n"
        f"{json.dumps(meta_public, default=str)}\n\n"
        "=== FULL TRACE (truncated) ===\n"
        f"{json.dumps(prompt_log, default=str)[:2500]}\n\n"
        "Required reasoning order:\n"
        "Step 1 (Planner Check): Did the Planner add impossible/hallucinated constraints "
        "not present in the User Task?\n"
        "Step 2 (Coder Check): Did the Coder introduce independent syntax errors, or only "
        "follow bad Planner/Reviewer instructions?\n"
        "Step 3 (Reviewer Check): Did the Reviewer demand a harmful rewrite "
        "(while True: pass / DESTRUCTIVE_REVIEW_ADVICE)?\n"
        "Step 4 (Root Cause): Who initiated the failure chain?\n"
        "Step 5 (JSON): Emit the attribution JSON object last.\n"
        "If global_reward is 1.0 and there is no fault signal, set highest_blame to \"none\".\n"
        "Never blame Executor solely for surfacing an upstream fault."
    )
    llm = llm_call(prompt, role="meta_agent", temperature=0.0)

    try:
        parsed = parse_meta_attribution_json(llm.content)
        attribution = parsed["attribution"]
        highest = parsed["highest_blame"]
        rationale = parsed["rationale"] or (
            f"Meta-Agent attributed primary failure to '{highest}'."
        )
    except Exception:  # noqa: BLE001
        attribution = mock_meta_attribution_json(prompt_log)
        if float(reward or 0) >= 1.0:
            highest = "none"
        else:
            highest = max(attribution.items(), key=lambda kv: kv[1])[0]
        rationale = (
            f"Parse fallback; attributed '{highest}' "
            f"with score {attribution.get(highest, 0):.3f}."
        )

    return {
        "attribution": attribution,
        "highest_blame": highest,
        "rationale": rationale,
        "raw_llm": llm.content,
        "latency_ms": llm.latency_ms,
        "model": llm.model,
    }


def precision_at_1(
    predicted_highest_blame: str,
    actual_poisoned_node: str | None,
) -> float:
    """
    Precision@1 for fault localization.

    Clean runs (no poison): score 1.0 only if prediction is none/empty.
    """
    if actual_poisoned_node is None or str(actual_poisoned_node).upper() == "NONE":
        return (
            1.0
            if not predicted_highest_blame
            or predicted_highest_blame.lower() in {"none", "n/a", ""}
            else 0.0
        )
    return (
        1.0
        if predicted_highest_blame.lower() == actual_poisoned_node.lower()
        else 0.0
    )


def evaluate_meta_agent(
    trace: AgentState,
    meta_response: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare Meta-Agent prediction against FaultInjector ground truth."""
    response = meta_response or approximate_credit_assignment(trace)
    predicted = response["highest_blame"]
    actual = trace.poisoned_node
    p_at_1 = precision_at_1(predicted, actual)
    return {
        "predicted_highest_blame": predicted,
        "actual_poisoned_node": actual,
        "precision_at_1": p_at_1,
        "attribution": response["attribution"],
        "rationale": response.get("rationale", ""),
        "model": response.get("model"),
    }
