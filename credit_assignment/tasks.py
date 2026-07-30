"""Task dataset loaders for batch credit-assignment experiments."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class SoftwareTask(BaseModel):
    task_id: str
    prompt: str
    entry_point: str = "solve"
    test_cases: list[dict[str, Any]] = Field(default_factory=list)
    reference_solution: str = ""
    source: str = "custom"


def default_tasks() -> list[SoftwareTask]:
    """Compact HumanEval-style / custom software prompts with unit tests."""
    return [
        SoftwareTask(
            task_id="return_ok",
            prompt=(
                "Write a Python function solve() that returns the string 'ok' "
                "with no side effects."
            ),
            entry_point="solve",
            test_cases=[{"call": "solve()", "expected": "ok"}],
            reference_solution="def solve():\n    return 'ok'\n",
        ),
        SoftwareTask(
            task_id="add_two",
            prompt=(
                "Write a Python function add(a, b) that returns the sum of two numbers."
            ),
            entry_point="add",
            test_cases=[
                {"call": "add(2, 3)", "expected": 5},
                {"call": "add(-1, 1)", "expected": 0},
                {"call": "add(0, 0)", "expected": 0},
            ],
            reference_solution="def add(a, b):\n    return a + b\n",
        ),
        SoftwareTask(
            task_id="is_even",
            prompt=(
                "Write a Python function is_even(n) that returns True if n is even, "
                "otherwise False."
            ),
            entry_point="is_even",
            test_cases=[
                {"call": "is_even(2)", "expected": True},
                {"call": "is_even(3)", "expected": False},
                {"call": "is_even(0)", "expected": True},
            ],
            reference_solution="def is_even(n):\n    return n % 2 == 0\n",
        ),
        SoftwareTask(
            task_id="factorial",
            prompt=(
                "Write a Python function factorial(n) that returns n! for n >= 0. "
                "Use an iterative or recursive implementation."
            ),
            entry_point="factorial",
            test_cases=[
                {"call": "factorial(0)", "expected": 1},
                {"call": "factorial(1)", "expected": 1},
                {"call": "factorial(5)", "expected": 120},
            ],
            reference_solution=(
                "def factorial(n):\n"
                "    r = 1\n"
                "    for i in range(2, n + 1):\n"
                "        r *= i\n"
                "    return r\n"
            ),
        ),
        SoftwareTask(
            task_id="reverse_string",
            prompt=(
                "Write a Python function reverse_string(s) that returns the reverse "
                "of string s."
            ),
            entry_point="reverse_string",
            test_cases=[
                {"call": "reverse_string('abc')", "expected": "cba"},
                {"call": "reverse_string('')", "expected": ""},
                {"call": "reverse_string('x')", "expected": "x"},
            ],
            reference_solution="def reverse_string(s):\n    return s[::-1]\n",
        ),
        SoftwareTask(
            task_id="max_of_three",
            prompt=(
                "Write a Python function max_of_three(a, b, c) that returns the "
                "largest of three numbers."
            ),
            entry_point="max_of_three",
            test_cases=[
                {"call": "max_of_three(1, 2, 3)", "expected": 3},
                {"call": "max_of_three(9, 2, 3)", "expected": 9},
                {"call": "max_of_three(-1, -5, -3)", "expected": -1},
            ],
            reference_solution="def max_of_three(a, b, c):\n    return max(a, b, c)\n",
        ),
        SoftwareTask(
            task_id="count_vowels",
            prompt=(
                "Write a Python function count_vowels(s) that counts vowels "
                "a,e,i,o,u (case-insensitive) in s."
            ),
            entry_point="count_vowels",
            test_cases=[
                {"call": "count_vowels('hello')", "expected": 2},
                {"call": "count_vowels('xyz')", "expected": 0},
                {"call": "count_vowels('AEIOU')", "expected": 5},
            ],
            reference_solution=(
                "def count_vowels(s):\n"
                "    return sum(1 for ch in s.lower() if ch in 'aeiou')\n"
            ),
        ),
        SoftwareTask(
            task_id="fizzbuzz_one",
            prompt=(
                "Write a Python function fizzbuzz(n) that returns 'Fizz' if n divisible "
                "by 3, 'Buzz' if by 5, 'FizzBuzz' if by both, else str(n)."
            ),
            entry_point="fizzbuzz",
            test_cases=[
                {"call": "fizzbuzz(3)", "expected": "Fizz"},
                {"call": "fizzbuzz(5)", "expected": "Buzz"},
                {"call": "fizzbuzz(15)", "expected": "FizzBuzz"},
                {"call": "fizzbuzz(7)", "expected": "7"},
            ],
            reference_solution=(
                "def fizzbuzz(n):\n"
                "    if n % 15 == 0:\n"
                "        return 'FizzBuzz'\n"
                "    if n % 3 == 0:\n"
                "        return 'Fizz'\n"
                "    if n % 5 == 0:\n"
                "        return 'Buzz'\n"
                "    return str(n)\n"
            ),
        ),
        SoftwareTask(
            task_id="unique_sorted",
            prompt=(
                "Write a Python function unique_sorted(xs) that returns a sorted list "
                "of unique elements from list xs."
            ),
            entry_point="unique_sorted",
            test_cases=[
                {"call": "unique_sorted([3,1,2,1])", "expected": [1, 2, 3]},
                {"call": "unique_sorted([])", "expected": []},
                {"call": "unique_sorted([2,2,2])", "expected": [2]},
            ],
            reference_solution="def unique_sorted(xs):\n    return sorted(set(xs))\n",
        ),
        SoftwareTask(
            task_id="palindrome",
            prompt=(
                "Write a Python function is_palindrome(s) that returns True if s is a "
                "palindrome (ignore spaces, case-sensitive as given)."
            ),
            entry_point="is_palindrome",
            test_cases=[
                {"call": "is_palindrome('aba')", "expected": True},
                {"call": "is_palindrome('ab')", "expected": False},
                {"call": "is_palindrome('')", "expected": True},
            ],
            reference_solution="def is_palindrome(s):\n    return s == s[::-1]\n",
        ),
    ]


def ensure_tasks_file(path: Path | None = None) -> Path:
    path = path or (DATA_DIR / "tasks.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        payload = [t.model_dump() for t in default_tasks()]
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_tasks(path: Path | str | None = None) -> list[SoftwareTask]:
    """Load tasks from JSON, creating the default dataset if missing."""
    tasks_path = ensure_tasks_file(Path(path) if path else None)
    raw = json.loads(tasks_path.read_text(encoding="utf-8"))
    return [SoftwareTask.model_validate(item) for item in raw]


def try_load_humaneval(limit: int = 20) -> list[SoftwareTask]:
    """
    Optionally load HumanEval via the `datasets` / `human_eval` packages.
    Returns [] if unavailable.
    """
    try:
        from human_eval.data import read_problems  # type: ignore
    except Exception:
        return []

    problems = read_problems()
    out: list[SoftwareTask] = []
    for i, (pid, prob) in enumerate(problems.items()):
        if i >= limit:
            break
        # HumanEval uses canonical_solution + test harness; we keep prompt + entry
        out.append(
            SoftwareTask(
                task_id=str(pid),
                prompt=str(prob.get("prompt", "")),
                entry_point=str(prob.get("entry_point", "solution")),
                test_cases=[],  # full HumanEval checks need the official check() harness
                reference_solution=str(prob.get("canonical_solution", "")),
                source="humaneval",
            )
        )
    return out
