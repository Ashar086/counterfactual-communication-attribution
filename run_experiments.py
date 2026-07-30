#!/usr/bin/env python3
"""
Batch experiment loop for credit assignment evaluation.

Iterates a task dataset, injects synthetic faults across N runs, logs JSONL
traces, and reports Precision@1 + failure rates.

Examples:
  python run_experiments.py --n-runs 100
  python run_experiments.py --n-runs 12 --mock
  python run_experiments.py --n-runs 100 --modes POISON_CODER,POISON_PLANNER
"""

from __future__ import annotations

import argparse
import json
import random
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from credit_assignment.fault_injection import FaultInjector, PoisonMode
from credit_assignment.graph import run_pipeline
from credit_assignment.llm import _load_dotenv, use_mock_llm
from credit_assignment.meta_agent import approximate_credit_assignment, evaluate_meta_agent
from credit_assignment.tasks import SoftwareTask, load_tasks


def _parse_modes(raw: str) -> list[PoisonMode]:
    modes: list[PoisonMode] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        modes.append(PoisonMode(part))
    return modes or [
        PoisonMode.NONE,
        PoisonMode.POISON_PLANNER,
        PoisonMode.POISON_CODER,
        PoisonMode.POISON_REVIEWER,
    ]


def _run_one(
    *,
    run_id: int,
    task: SoftwareTask,
    mode: PoisonMode,
    seed: int,
) -> dict[str, Any]:
    injector = FaultInjector(mode=mode)
    t0 = time.perf_counter()
    state = run_pipeline(
        task.prompt,
        fault_injector=injector,
        entry_point=task.entry_point,
        test_cases=task.test_cases,
        reference_solution=task.reference_solution,
    )
    pipeline_ms = round((time.perf_counter() - t0) * 1000, 3)

    meta = approximate_credit_assignment(state)
    evaluation = evaluate_meta_agent(state, meta)

    failed = float(state.global_reward) < 1.0
    return {
        "run_id": run_id,
        "seed": seed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task_id": task.task_id,
        "task_source": task.source,
        "entry_point": task.entry_point,
        "poison_mode": mode.value,
        "poisoned_node": state.poisoned_node,
        "global_reward": state.global_reward,
        "failed": failed,
        "review_status": state.review_status,
        "execution_result": state.execution_result,
        "pipeline_latency_ms": pipeline_ms,
        "plan": state.plan,
        "code": state.code,
        "trace_log": state.trace_log,
        "meta_agent": {
            "attribution": meta.get("attribution"),
            "highest_blame": meta.get("highest_blame"),
            "rationale": meta.get("rationale"),
            "model": meta.get("model"),
            "latency_ms": meta.get("latency_ms"),
        },
        "evaluation": evaluation,
        "precision_at_1": evaluation["precision_at_1"],
        "mock_llm": use_mock_llm(),
    }


def run_experiments(
    *,
    n_runs: int,
    modes: list[PoisonMode],
    tasks: list[SoftwareTask],
    seed: int,
    out_dir: Path,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    jsonl_path = out_dir / f"runs_{stamp}.jsonl"
    summary_path = out_dir / f"summary_{stamp}.json"

    rng = random.Random(seed)
    records: list[dict[str, Any]] = []

    print(f"Running {n_runs} experiments | mock_llm={use_mock_llm()} | modes={[m.value for m in modes]}", flush=True)
    print(f"Logging to {jsonl_path}", flush=True)

    with jsonl_path.open("w", encoding="utf-8") as fh:
        for i in range(n_runs):
            task = tasks[i % len(tasks)]
            mode = modes[i % len(modes)]
            # Prefer poisoned modes for attribution eval: skip over-weighting NONE
            # when user asked for fault injection across 100+ runs — still include NONE
            # periodically via the cycling modes list.
            run_seed = rng.randint(0, 10**9)
            try:
                record = _run_one(run_id=i, task=task, mode=mode, seed=run_seed)
            except Exception as exc:  # noqa: BLE001
                record = {
                    "run_id": i,
                    "task_id": task.task_id,
                    "poison_mode": mode.value,
                    "error": f"{type(exc).__name__}: {exc}",
                    "failed": True,
                    "precision_at_1": 0.0,
                    "global_reward": 0.0,
                }
            records.append(record)
            fh.write(json.dumps(record, default=str) + "\n")
            fh.flush()
            status = "FAIL" if record.get("failed") else "OK"
            print(
                f"[{i+1:04d}/{n_runs}] {status} task={task.task_id} "
                f"mode={mode.value} R={record.get('global_reward')} "
                f"P@1={record.get('precision_at_1')} "
                f"blame={record.get('meta_agent', {}).get('highest_blame')}",
                flush=True,
            )

    summary = _summarize(records, modes=modes)
    summary["jsonl_path"] = str(jsonl_path)
    summary["n_runs"] = n_runs
    summary["seed"] = seed
    summary["mock_llm"] = use_mock_llm()
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\n=== Summary ===")
    print(json.dumps(summary, indent=2))
    print(f"\nWrote {summary_path}")
    return summary


def _summarize(records: list[dict[str, Any]], *, modes: list[PoisonMode]) -> dict[str, Any]:
    n = len(records) or 1
    failures = sum(1 for r in records if r.get("failed"))
    p_at_1_vals = [float(r.get("precision_at_1", 0.0)) for r in records]
    by_mode: dict[str, dict[str, Any]] = {}

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        grouped[str(r.get("poison_mode", "UNKNOWN"))].append(r)

    for mode, rows in grouped.items():
        m_n = len(rows) or 1
        by_mode[mode] = {
            "n": len(rows),
            "failure_rate": sum(1 for r in rows if r.get("failed")) / m_n,
            "precision_at_1": sum(float(r.get("precision_at_1", 0.0)) for r in rows) / m_n,
            "mean_reward": sum(float(r.get("global_reward", 0.0)) for r in rows) / m_n,
            "blame_counts": dict(Counter(str((r.get("meta_agent") or {}).get("highest_blame")) for r in rows)),
        }

    # Attribution metrics only on poisoned runs (where ground truth exists)
    poisoned = [r for r in records if r.get("poisoned_node")]
    p_n = len(poisoned) or 1

    return {
        "overall": {
            "n": len(records),
            "failure_rate": failures / n,
            "precision_at_1": sum(p_at_1_vals) / n,
            "mean_reward": sum(float(r.get("global_reward", 0.0)) for r in records) / n,
        },
        "poisoned_only": {
            "n": len(poisoned),
            "precision_at_1": sum(float(r.get("precision_at_1", 0.0)) for r in poisoned) / p_n,
            "failure_rate": sum(1 for r in poisoned if r.get("failed")) / p_n,
        },
        "by_mode": by_mode,
        "modes_requested": [m.value for m in modes],
    }


def main() -> None:
    _load_dotenv()
    parser = argparse.ArgumentParser(description="Credit assignment batch experiments")
    parser.add_argument("--n-runs", type=int, default=100, help="Number of pipeline runs")
    parser.add_argument(
        "--modes",
        type=str,
        default="POISON_PLANNER,POISON_CODER,POISON_REVIEWER,NONE",
        help="Comma-separated PoisonMode values to cycle",
    )
    parser.add_argument("--tasks", type=str, default="", help="Path to tasks.json")
    parser.add_argument("--out-dir", type=str, default="results", help="Output directory")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Force USE_MOCK_LLM=1 (no OpenAI calls)",
    )
    args = parser.parse_args()

    if args.mock:
        import os

        os.environ["USE_MOCK_LLM"] = "1"

    tasks_path = Path(args.tasks) if args.tasks else None
    tasks = load_tasks(tasks_path)
    modes = _parse_modes(args.modes)

    run_experiments(
        n_runs=args.n_runs,
        modes=modes,
        tasks=tasks,
        seed=args.seed,
        out_dir=Path(args.out_dir),
    )


if __name__ == "__main__":
    main()
