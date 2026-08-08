"""Load SWE-bench Verified subset (HuggingFace)."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field


class SWEBenchInstance(BaseModel):
    instance_id: str
    problem_statement: str
    repo: str = ""
    base_commit: str = ""
    gold_patch: str = ""
    fail_to_pass: list[str] = Field(default_factory=list)
    pass_to_pass: list[str] = Field(default_factory=list)
    difficulty: str = ""
    hints_text: str = ""

    model_config = {"extra": "forbid"}


def _parse_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str):
        try:
            val = json.loads(raw)
            if isinstance(val, list):
                return [str(x) for x in val]
        except json.JSONDecodeError:
            return [raw] if raw.strip() else []
    return []


def row_to_instance(row: dict[str, Any], *, truncate_problem: bool = True) -> SWEBenchInstance:
    ps = str(row.get("problem_statement") or "")
    # Cap very long statements for overnight LLM runs (shaped pilot). Official VI.B: no truncate.
    if truncate_problem and len(ps) > 8000:
        ps = ps[:8000] + "\n\n[truncated for CommSCM Part VI]"
    return SWEBenchInstance(
        instance_id=str(row.get("instance_id") or "unknown"),
        problem_statement=ps,
        repo=str(row.get("repo") or ""),
        base_commit=str(row.get("base_commit") or ""),
        gold_patch=str(row.get("patch") or ""),
        fail_to_pass=_parse_list(row.get("FAIL_TO_PASS")),
        pass_to_pass=_parse_list(row.get("PASS_TO_PASS")),
        difficulty=str(row.get("difficulty") or ""),
        hints_text=str(row.get("hints_text") or "")[:2000],
    )


def load_swebench_verified_subset(
    n: int = 8,
    *,
    seed: int = 42,
    dataset_name: str = "princeton-nlp/SWE-bench_Verified",
    split: str = "test",
) -> list[SWEBenchInstance]:
    """
    Load a deterministic subset of SWE-bench Verified.

    Requires ``datasets`` + network on first download.
    """
    from datasets import load_dataset

    ds = load_dataset(dataset_name, split=split)
    # Prefer easier instances when difficulty is present
    rows = list(ds)
    easy = [r for r in rows if str(r.get("difficulty") or "").startswith("1")]
    pool = easy if len(easy) >= n else rows
    # Deterministic shuffle via seed
    import random

    rng = random.Random(seed)
    order = list(range(len(pool)))
    rng.shuffle(order)
    selected = [pool[i] for i in order[:n]]
    return [row_to_instance(dict(r)) for r in selected]


def load_swebench_verified_by_ids(
    instance_ids: list[str],
    *,
    dataset_name: str = "princeton-nlp/SWE-bench_Verified",
    split: str = "test",
    truncate_problem: bool = False,
) -> list[SWEBenchInstance]:
    """
    Load exact Verified instances by id (Part VI.B).

    Preserves ``instance_ids`` order. Does not apply easy-difficulty filtering.
    Official VI.B: ``truncate_problem=False``.
    """
    from datasets import load_dataset

    ds = load_dataset(dataset_name, split=split)
    by_id = {str(r["instance_id"]): dict(r) for r in ds}
    missing = [i for i in instance_ids if i not in by_id]
    if missing:
        raise KeyError(f"Missing Verified instance ids: {missing[:5]}...")
    return [
        row_to_instance(by_id[i], truncate_problem=truncate_problem) for i in instance_ids
    ]


def offline_fixture_instances(n: int = 3) -> list[SWEBenchInstance]:
    """Tiny offline fixtures when HF download is unavailable (unit tests)."""
    fixtures = [
        SWEBenchInstance(
            instance_id="fixture__repo-1",
            problem_statement=(
                "Bug: function `add(a, b)` returns a-b instead of a+b. "
                "Provide a minimal unified diff patch fixing add()."
            ),
            repo="fixture/repo",
            gold_patch="--- a/mathlib.py\n+++ b/mathlib.py\n@@\n-def add(a,b): return a-b\n+def add(a,b): return a+b\n",
            fail_to_pass=["test_add"],
            difficulty="1-15",
        ),
        SWEBenchInstance(
            instance_id="fixture__repo-2",
            problem_statement=(
                "Bug: `is_even(n)` returns True for odds. Fix the parity check."
            ),
            repo="fixture/repo",
            gold_patch="--- a/util.py\n+++ b/util.py\n@@\n-def is_even(n): return n % 2 == 1\n+def is_even(n): return n % 2 == 0\n",
            fail_to_pass=["test_even"],
            difficulty="1-15",
        ),
        SWEBenchInstance(
            instance_id="fixture__repo-3",
            problem_statement=(
                "Bug: `greet(name)` returns 'hello' without the name. "
                "It should return f'hello {name}'."
            ),
            repo="fixture/repo",
            gold_patch="--- a/hi.py\n+++ b/hi.py\n@@\n-def greet(name): return 'hello'\n+def greet(name): return f'hello {name}'\n",
            fail_to_pass=["test_greet"],
            difficulty="1-15",
        ),
    ]
    return fixtures[:n]
