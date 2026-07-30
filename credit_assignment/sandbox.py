"""Subprocess sandbox for scoring generated Python against test cases."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SECRET_ENV_PREFIXES = ("OPENAI_", "AWS_", "AZURE_", "ANTHROPIC_", "HF_", "GITHUB_")

_RUNNER_SOURCE = r'''
import json
import traceback
from pathlib import Path

NAMESPACE = {}
SOURCE = Path("solution.py").read_text(encoding="utf-8")
TESTS = json.loads(Path("tests.json").read_text(encoding="utf-8"))
ENTRY = Path("entry_point.txt").read_text(encoding="utf-8").strip()

report = {"passed": 0, "total": len(TESTS), "failures": [], "error": None}

try:
    exec(compile(SOURCE, "<generated>", "exec"), NAMESPACE, NAMESPACE)
except Exception as exc:
    report["error"] = f"import/exec error: {type(exc).__name__}: {exc}"
    print(json.dumps(report))
    raise SystemExit(0)

fn = NAMESPACE.get(ENTRY)
if fn is None or not callable(fn):
    report["error"] = f"missing entry point: {ENTRY}"
    print(json.dumps(report))
    raise SystemExit(0)

for i, case in enumerate(TESTS):
    call = case.get("call")
    expected = case.get("expected")
    args = case.get("args", [])
    kwargs = case.get("kwargs", {})
    try:
        if call:
            got = eval(call, NAMESPACE, NAMESPACE)
        else:
            got = fn(*args, **kwargs)
        if got != expected:
            report["failures"].append({
                "index": i,
                "call": call or f"{ENTRY}(*{args}, **{kwargs})",
                "expected": expected,
                "got": repr(got),
            })
        else:
            report["passed"] += 1
    except Exception as exc:
        report["failures"].append({
            "index": i,
            "call": call,
            "error": f"{type(exc).__name__}: {exc}",
            "trace": traceback.format_exc()[-400:],
        })

print(json.dumps(report))
'''


@dataclass(frozen=True)
class SandboxResult:
    reward: float
    passed: int
    total: int
    stdout: str
    stderr: str
    timed_out: bool
    issues: list[str]

    @property
    def summary(self) -> str:
        status = "PASS" if self.reward >= 1.0 and self.total > 0 else "FAIL"
        bits = [
            f"{status}: {self.passed}/{self.total} tests",
            f"reward={self.reward:.4f}",
        ]
        if self.timed_out:
            bits.append("timeout")
        if self.issues:
            bits.append("issues=" + ",".join(self.issues))
        detail = (self.stderr or self.stdout or "").strip()
        if detail:
            bits.append(detail[:500])
        return " | ".join(bits)


def _sandbox_env() -> dict[str, str]:
    """Inherit a minimal parent env without API secrets."""
    env: dict[str, str] = {}
    for key, value in os.environ.items():
        upper = key.upper()
        if upper.startswith(_SECRET_ENV_PREFIXES) or upper == "OPENAI_API_KEY":
            continue
        env[key] = value
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def run_in_sandbox(
    code: str,
    test_cases: list[dict[str, Any]] | None,
    *,
    entry_point: str = "solve",
    timeout_sec: float = 5.0,
) -> SandboxResult:
    """
    Execute `code` in an isolated Python subprocess and score against tests.

    Reward R = passed / total. Syntax / missing entry point → R = 0.
    """
    issues: list[str] = []
    cases = list(test_cases or [])
    if not cases:
        cases = [{"call": f"{entry_point}()", "expected": "ok"}]

    if not code.strip():
        return SandboxResult(
            reward=0.0,
            passed=0,
            total=len(cases),
            stdout="",
            stderr="empty code",
            timed_out=False,
            issues=["empty_code"],
        )

    with tempfile.TemporaryDirectory(prefix="ca_sandbox_") as tmp:
        root = Path(tmp)
        (root / "solution.py").write_text(code, encoding="utf-8")
        (root / "tests.json").write_text(json.dumps(cases), encoding="utf-8")
        (root / "entry_point.txt").write_text(entry_point, encoding="utf-8")
        (root / "runner.py").write_text(_RUNNER_SOURCE, encoding="utf-8")

        try:
            proc = subprocess.run(
                [sys.executable, str(root / "runner.py")],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                cwd=tmp,
                env=_sandbox_env(),
            )
        except subprocess.TimeoutExpired as exc:
            return SandboxResult(
                reward=0.0,
                passed=0,
                total=len(cases),
                stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
                stderr="timeout",
                timed_out=True,
                issues=["timeout"],
            )

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    report: dict[str, Any] | None = None
    for line in reversed(stdout.strip().splitlines() or [""]):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                report = json.loads(line)
                break
            except json.JSONDecodeError:
                continue

    if report is None:
        issues.append("no_report")
        if proc.returncode != 0:
            issues.append("nonzero_exit")
        return SandboxResult(
            reward=0.0,
            passed=0,
            total=len(cases),
            stdout=stdout,
            stderr=stderr or "failed to parse sandbox report",
            timed_out=False,
            issues=issues,
        )

    if report.get("error"):
        issues.append("runtime_error")
        return SandboxResult(
            reward=0.0,
            passed=0,
            total=int(report.get("total") or len(cases)),
            stdout=stdout,
            stderr=str(report["error"]),
            timed_out=False,
            issues=issues,
        )

    passed = int(report.get("passed", 0))
    total = int(report.get("total") or len(cases))
    reward = (passed / total) if total else 0.0
    if passed < total:
        issues.append("test_failures")
    return SandboxResult(
        reward=float(reward),
        passed=passed,
        total=total,
        stdout=stdout,
        stderr=json.dumps(report.get("failures") or [])[:800],
        timed_out=False,
        issues=issues,
    )
