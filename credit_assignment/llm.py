"""LLM client: OpenAI-backed agents with optional mock fallback."""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Load .env from project root if present (no hard dependency on python-dotenv).
_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def _load_dotenv(path: Path = _ENV_PATH) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()


@dataclass(frozen=True)
class LLMResponse:
    content: str
    latency_ms: float
    model: str


# Back-compat alias used by older imports / demos
MockLLMResponse = LLMResponse

BASE_MODEL = os.getenv("OPENAI_BASE_MODEL", "gpt-4o-mini")
META_MODEL = os.getenv("OPENAI_META_MODEL", "gpt-4o")


def use_mock_llm() -> bool:
    flag = os.getenv("USE_MOCK_LLM", "0").strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return True
    if flag in {"0", "false", "no", "off"}:
        return not bool(os.getenv("OPENAI_API_KEY"))
    return not bool(os.getenv("OPENAI_API_KEY"))


def _seeded_rng(seed_material: str) -> random.Random:
    digest = hashlib.sha256(seed_material.encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


_SYSTEM_PROMPTS: dict[str, str] = {
    "planner": (
        "You are the Planner in a software-generation pipeline. "
        "Given a task, produce a concise step-by-step plan for implementing a Python "
        "function. Do not write the full implementation. Mention the required entry "
        "point name if specified."
    ),
    "coder": (
        "You are the Coder in a software-generation pipeline. "
        "Implement the plan as valid Python code only. Prefer a single fenced "
        "```python``` block. Include the required entry-point function. "
        "No explanations outside the code fence."
    ),
    "reviewer": (
        "You are the Reviewer in a software-generation pipeline. "
        "Inspect the code for syntax errors, missing entry points, and constraint "
        "violations. End your reply with exactly one line: "
        "VERDICT: Approved  OR  VERDICT: Rejected"
    ),
    "meta_agent": (
        "You are a Meta-Agent for credit assignment in a compound agentic system "
        "(Planner, Coder, Reviewer, Executor).\n\n"
        "You MUST perform Counterfactual Chain-of-Thought before scoring.\n"
        "Follow these steps in order in your reply:\n"
        "Step 1 (Planner Check): Compare the Planner's output to the original User Task. "
        "Did the Planner add impossible, hallucinated, or out-of-scope constraints "
        "(e.g. IMPOSSIBLE_CONSTRAINT markers)?\n"
        "Step 2 (Coder Check): Did the Coder introduce its own syntax/logic errors, "
        "or was it following bad instructions from the Planner or Reviewer?\n"
        "Step 3 (Reviewer Check): Did the Reviewer demand a harmful rewrite "
        "(e.g. while True: pass / DESTRUCTIVE_REVIEW_ADVICE)? If the Coder only "
        "applied reviewer advice, blame the Reviewer, not the Coder.\n"
        "Step 4 (Root Cause): Who initiated the failure chain?\n"
        "Step 5 (JSON): After the steps above, output ONLY a final JSON object:\n"
        '{"attribution":{"planner":0.0,"coder":0.0,"reviewer":0.0,"executor":0.0},'
        '"highest_blame":"planner","rationale":"..."}\n'
        "Scores in [0,1]. highest_blame must be one of planner|coder|reviewer|executor "
        "(or \"none\" if the run truly succeeded with reward 1.0 and no injected fault).\n"
        "Do not blame the Executor merely for reporting a failure caused upstream."
    ),
}


def _build_user_message(prompt: str, role: str, override: str | None) -> str:
    parts: list[str] = []
    if override:
        parts.append(f"Additional system/prompt override for this node:\n{override}\n")
    if role == "planner":
        parts.append(f"Task:\n{prompt}")
    elif role == "coder":
        parts.append(f"Plan / specification:\n{prompt}")
    elif role == "reviewer":
        parts.append(f"Code under review:\n{prompt}")
    else:
        parts.append(prompt)
    return "\n".join(parts)


def _openai_chat(
    *,
    system: str,
    user: str,
    model: str,
    temperature: float,
    seed: int | None = None,
) -> LLMResponse:
    from openai import OpenAI

    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        timeout=float(os.getenv("OPENAI_TIMEOUT_SEC", "60")),
        max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "2")),
    )
    t0 = time.perf_counter()
    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if seed is not None:
        kwargs["seed"] = seed
    completion = client.chat.completions.create(**kwargs)
    latency_ms = round((time.perf_counter() - t0) * 1000, 3)
    content = (completion.choices[0].message.content or "").strip()
    return LLMResponse(content=content, latency_ms=latency_ms, model=model)


def mock_llm_call(
    prompt: str,
    *,
    role: str,
    override: str | None = None,
    temperature: float = 0.0,
) -> LLMResponse:
    """Deterministic mock LLM (offline / CI)."""
    t0 = time.perf_counter()
    rng = _seeded_rng(f"{role}|{prompt}|{override or ''}|{temperature}")
    prefix = f"[prompt={override}] " if override else ""

    if role == "coder" and override and override.startswith("DEGRADED:"):
        content = (
            f"{prefix}# Degraded generation (bad prompt)\n"
            f"result = 'ok'  # missing required solve() entrypoint\n"
        )
    elif role == "coder" and override and override.startswith("HARDENED:"):
        content = (
            f"{prefix}# Hardened generation (shadow / updated prompt)\n"
            f"def solve():\n"
            f"    return 'ok'\n"
        )
    else:
        templates: dict[str, str] = {
            "planner": (
                f"{prefix}PLAN:\n"
                f"1. Parse requirements from: {prompt[:120]}\n"
                f"2. Emit the required entry-point function.\n"
                f"3. Constraints: pure function, no network I/O."
            ),
            "coder": (
                f"{prefix}```python\n"
                f"def solve():\n"
                f"    # task hash={rng.randint(1000, 9999)}\n"
                f"    return 'ok'\n"
                f"```"
            ),
            "reviewer": (
                f"{prefix}REVIEW: Looking for syntax errors and constraint violations.\n"
                f"VERDICT: Approved"
            ),
            "meta_agent": json.dumps(
                {
                    "attribution": {
                        "planner": 0.1,
                        "coder": 0.1,
                        "reviewer": 0.1,
                        "executor": 0.05,
                    },
                    "highest_blame": "none",
                    "rationale": "mock default",
                }
            ),
        }
        content = templates.get(role, f"{prefix}echo: {prompt[:200]}")

    latency_ms = round((time.perf_counter() - t0) * 1000 + rng.uniform(0.5, 3.0), 3)
    return LLMResponse(content=content, latency_ms=latency_ms, model="mock-llm-v0")


def llm_call(
    prompt: str,
    *,
    role: str,
    override: str | None = None,
    temperature: float | None = None,
    model: str | None = None,
    seed: int | None = None,
) -> LLMResponse:
    """
    Call an LLM for a pipeline role.

    Base agents (planner/coder/reviewer) → gpt-4o-mini by default.
    Meta-Agent → gpt-4o by default.
    Set USE_MOCK_LLM=1 to force mocks.

    Temperature/seed default from LLM_TEMPERATURE / LLM_SEED env when unset
    (Week-5 live stochasticity sweeps).
    """
    if temperature is None:
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.0"))
    if seed is None and os.getenv("LLM_SEED", "").strip():
        seed = int(os.environ["LLM_SEED"])

    resolved_model = model or (META_MODEL if role == "meta_agent" else BASE_MODEL)

    # Synthetic shadow-buffer prompt tags stay deterministic even with a live API.
    if override and override.startswith(("DEGRADED:", "HARDENED:")):
        return mock_llm_call(
            prompt, role=role, override=override, temperature=temperature
        )

    if use_mock_llm():
        return mock_llm_call(
            prompt, role=role, override=override, temperature=temperature
        )

    system = _SYSTEM_PROMPTS.get(role, "You are a helpful assistant.")
    if override:
        system = f"{system}\n\nPrompt update:\n{override}"

    user = _build_user_message(prompt, role, override)
    try:
        return _openai_chat(
            system=system,
            user=user,
            model=resolved_model,
            temperature=temperature,
            seed=seed,
        )
    except Exception as exc:  # noqa: BLE001 — fall back so experiments keep running
        if os.getenv("FAIL_ON_LLM_ERROR", "").strip().lower() in {"1", "true", "yes", "on"}:
            raise
        fallback = mock_llm_call(
            prompt, role=role, override=override, temperature=temperature
        )
        return LLMResponse(
            content=fallback.content,
            latency_ms=fallback.latency_ms,
            model=f"mock-fallback:{type(exc).__name__}",
        )


def extract_python_code(text: str) -> str:
    """Pull the first Python fenced block, else return stripped text."""
    fence = re.search(r"```(?:python)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    if fence:
        return fence.group(1).strip() + "\n"
    return text.strip() + "\n"


def parse_review_verdict(text: str) -> str:
    """Extract Approved / Rejected / NeedsRevision from reviewer output."""
    match = re.search(
        r"VERDICT:\s*(Approved|Rejected|NeedsRevision)", text, flags=re.IGNORECASE
    )
    if match:
        raw = match.group(1).lower()
        if raw == "approved":
            return "Approved"
        if raw == "needsrevision":
            return "NeedsRevision"
        return "Rejected"
    if re.search(r"\bNeedsRevision\b", text, flags=re.IGNORECASE):
        return "NeedsRevision"
    if re.search(r"\bRejected\b", text, flags=re.IGNORECASE):
        return "Rejected"
    if re.search(r"\bApproved\b", text, flags=re.IGNORECASE):
        return "Approved"
    return "Rejected"


def parse_meta_attribution_json(raw: str) -> dict[str, Any]:
    """Parse Meta-Agent JSON; tolerate markdown fences."""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Best-effort object extraction
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(text[start : end + 1])
        else:
            raise

    attribution = data.get("attribution") or {}
    agents = ("planner", "coder", "reviewer", "executor")
    cleaned = {
        a: float(max(0.0, min(1.0, float(attribution.get(a, 0.0))))) for a in agents
    }
    highest = str(data.get("highest_blame") or max(cleaned, key=cleaned.get)).lower()
    if highest not in agents and highest != "none":
        highest = max(cleaned, key=cleaned.get)
    return {
        "attribution": cleaned,
        "highest_blame": highest,
        "rationale": str(data.get("rationale") or ""),
    }


def mock_meta_attribution_json(
    trace_log: dict[str, Any], failure_hint: str | None = None
) -> dict[str, float]:
    """Heuristic fallback attribution for offline / parse failures."""
    scores = {"planner": 0.1, "coder": 0.1, "reviewer": 0.1, "executor": 0.05}
    plan = str((trace_log.get("planner") or {}).get("output", ""))
    code = str((trace_log.get("coder") or {}).get("output", ""))
    review = str((trace_log.get("reviewer") or {}).get("output", ""))
    reviser = str((trace_log.get("reviser") or {}).get("output", ""))
    exec_out = str((trace_log.get("executor") or {}).get("output", ""))

    if "IMPOSSIBLE_CONSTRAINT" in plan or "impossible" in plan.lower():
        # Root cause is planner; do not dump blame on executor for reporting it.
        scores["planner"] = 0.95
        scores["coder"] = 0.2
        scores["executor"] = 0.05
    if "SYNTAX_ERROR" in code or "@@@" in code:
        scores["coder"] = max(scores["coder"], 0.9)
        scores["reviewer"] = max(scores["reviewer"], 0.35)
    if (
        "DESTRUCTIVE_REVIEW" in review
        or "while True: pass" in review
        or "NeedsRevision" in review
        or (trace_log.get("reviser") or {}).get("destructive")
    ):
        scores["reviewer"] = 0.95
        scores["coder"] = 0.25  # followed bad advice
        scores["executor"] = 0.05
    if "while True" in code or "while True" in reviser:
        if "DESTRUCTIVE_REVIEW" in review or "NeedsRevision" in review:
            scores["reviewer"] = max(scores["reviewer"], 0.95)
            scores["coder"] = min(scores.get("coder", 0.25), 0.3)
    if "Approved" in review and ("SYNTAX_ERROR" in code or "@@@" in code):
        scores["reviewer"] = max(scores["reviewer"], 0.8)
    if "fail" in exec_out.lower() or "error" in exec_out.lower():
        # Mild signal only; upstream agents dominate when markers exist
        scores["executor"] = max(scores["executor"], 0.15)

    if failure_hint and failure_hint.lower() in scores:
        scores[failure_hint.lower()] = min(1.0, scores[failure_hint.lower()] + 0.05)

    return {k: round(min(1.0, max(0.0, v)), 4) for k, v in scores.items()}
