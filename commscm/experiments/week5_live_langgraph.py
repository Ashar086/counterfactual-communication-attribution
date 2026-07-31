"""
Week 5 live LangGraph validation — high-volume attribution only.

Reports P@1 plus:
  - attribution confidence (top1 ΔY − top2 ΔY)
  - pipeline / extract / replay / intervention failure counts
  - optional temperature/seed stochasticity matrix
  - optional Attribution Stability (K reps → top-1 agreement + Kendall τ)

Does not change Parts I–III algorithms. No CCAS edits. No H3.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from collections import defaultdict
from pathlib import Path

from credit_assignment.fault_injection import FaultInjector, PoisonMode
from credit_assignment.graph import run_pipeline
from credit_assignment.tasks import load_tasks
from commscm.attribution.subset import SubsetAttributionEngine
from commscm.estimators.replay import DescendantReplayEngine
from commscm.metrics.ranking_stability import summarize_stability_group
from commscm.traces.langgraph_extract import agent_state_to_run_trace, langgraph_reward_outcome
from commscm.traces.langgraph_mechanisms import make_langgraph_sticky_registry

AGENT_EVENTS = {"C1", "C2", "C3", "C4", "C5"}
MODES = (PoisonMode.POISON_PLANNER, PoisonMode.POISON_CODER, PoisonMode.POISON_REVIEWER)


def _reward_only_top1(rows: list) -> str | None:
    if not rows:
        return None
    return sorted(rows, key=lambda r: r.event_id, reverse=True)[0].event_id


def _random_top1(rows: list, seed: int) -> str | None:
    import random

    ids = [r.event_id for r in rows]
    return random.Random(seed).choice(ids) if ids else None


def _confidence(rows: list) -> float | None:
    if len(rows) < 2:
        return None
    ordered = sorted(rows, key=lambda r: (-r.delta_y, r.event_id))
    return float(ordered[0].delta_y - ordered[1].delta_y)


def score_trace(tr):
    mechs = make_langgraph_sticky_registry(tr.dag)
    return SubsetAttributionEngine(
        DescendantReplayEngine(langgraph_reward_outcome, mechs, structural_cost_iters=0),
        AGENT_EVENTS,
        name="LangGraphCR",
    ).score(tr)


def run_one(
    *,
    task,
    mode: PoisonMode,
    run_idx: int,
    temperature: float,
    seed: int | None,
) -> dict:
    os.environ["LLM_TEMPERATURE"] = str(temperature)
    if seed is not None:
        os.environ["LLM_SEED"] = str(seed)
    elif "LLM_SEED" in os.environ:
        del os.environ["LLM_SEED"]

    row: dict = {
        "run_idx": run_idx,
        "task_id": task.task_id,
        "poison_mode": mode.value,
        "temperature": temperature,
        "seed": seed,
        "pipeline_ok": False,
        "extract_ok": False,
        "attribution_ok": False,
        "failures": [],
    }
    t0 = time.perf_counter()
    try:
        state = run_pipeline(
            task.prompt,
            fault_injector=FaultInjector(mode=mode),
            entry_point=task.entry_point,
            test_cases=list(task.test_cases),
            reference_solution=task.reference_solution,
        )
        row["pipeline_ok"] = True
        row["global_reward"] = float(state.global_reward)
        row["poisoned_node"] = state.poisoned_node
    except Exception as exc:  # noqa: BLE001
        row["failures"].append({"stage": "pipeline", "error": f"{type(exc).__name__}: {exc}"})
        row["traceback"] = traceback.format_exc()[-1500:]
        row["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return row

    try:
        tr = agent_state_to_run_trace(
            state, run_id=f"live_{run_idx}_{mode.value}_{task.task_id}"
        )
        row["extract_ok"] = True
        row["gold"] = tr.gold_fault_event_id
        row["n_events"] = len(tr.dag.events)
    except Exception as exc:  # noqa: BLE001
        row["failures"].append({"stage": "extract", "error": f"{type(exc).__name__}: {exc}"})
        row["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return row

    try:
        report = score_trace(tr)
        row["attribution_ok"] = True
        ordered = sorted(report.rows, key=lambda r: (-r.delta_y, r.event_id))
        row["cr_top1"] = report.predicted_top1
        row["cr_ranking"] = [r.event_id for r in ordered]
        row["reward_only_top1"] = _reward_only_top1(report.rows)
        row["random_top1"] = _random_top1(report.rows, seed=run_idx)
        row["cr_hit"] = report.predicted_top1 == tr.gold_fault_event_id
        row["reward_only_hit"] = row["reward_only_top1"] == tr.gold_fault_event_id
        row["random_hit"] = row["random_top1"] == tr.gold_fault_event_id
        row["confidence_gap"] = _confidence(report.rows)
        row["top_deltas"] = [
            {"event_id": r.event_id, "delta_y": r.delta_y} for r in ordered[:5]
        ]
        # Intervention/replay soft failures: zero gap with multiple candidates
        if row["confidence_gap"] is not None and abs(row["confidence_gap"]) < 1e-12:
            row["failures"].append({"stage": "attribution", "error": "tie_or_zero_confidence_gap"})
    except Exception as exc:  # noqa: BLE001
        row["failures"].append(
            {"stage": "attribution", "error": f"{type(exc).__name__}: {exc}"}
        )
        row["traceback"] = traceback.format_exc()[-1500:]

    row["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return row


def aggregate(rows: list[dict]) -> dict:
    scored = [r for r in rows if r.get("attribution_ok")]
    n = len(scored)
    def rate(key: str) -> float:
        return sum(1 for r in scored if r.get(key)) / n if n else 0.0

    fail_stages: dict[str, int] = {}
    for r in rows:
        for f in r.get("failures") or []:
            fail_stages[f["stage"]] = fail_stages.get(f["stage"], 0) + 1

    confs = [r["confidence_gap"] for r in scored if r.get("confidence_gap") is not None]
    by_mode: dict[str, dict] = {}
    for mode in MODES:
        subset = [r for r in scored if r["poison_mode"] == mode.value]
        m = len(subset)
        by_mode[mode.value] = {
            "n": m,
            "cr_p_at_1": sum(1 for r in subset if r.get("cr_hit")) / m if m else 0.0,
            "reward_only_p_at_1": sum(1 for r in subset if r.get("reward_only_hit")) / m if m else 0.0,
            "random_p_at_1": sum(1 for r in subset if r.get("random_hit")) / m if m else 0.0,
        }

    return {
        "n_attempted": len(rows),
        "n_scored": n,
        "pipeline_ok_rate": sum(1 for r in rows if r.get("pipeline_ok")) / len(rows) if rows else 0.0,
        "extract_ok_rate": sum(1 for r in rows if r.get("extract_ok")) / len(rows) if rows else 0.0,
        "attribution_ok_rate": n / len(rows) if rows else 0.0,
        "cr_p_at_1": rate("cr_hit"),
        "reward_only_p_at_1": rate("reward_only_hit"),
        "random_p_at_1": rate("random_hit"),
        "mean_confidence_gap": sum(confs) / len(confs) if confs else None,
        "failure_counts_by_stage": fail_stages,
        "by_poison_mode": by_mode,
        "week5_live_gate_pass": (
            n > 0
            and rate("cr_hit") > rate("reward_only_hit")
            and rate("cr_hit") > rate("random_hit")
        ),
    }


def build_schedule(n_runs: int, tasks: list) -> list[tuple]:
    """Round-robin tasks × poison modes until n_runs."""
    schedule = []
    i = 0
    while len(schedule) < n_runs:
        task = tasks[i % len(tasks)]
        mode = MODES[i % len(MODES)]
        schedule.append((task, mode, len(schedule)))
        i += 1
    return schedule


def aggregate_stability(rows: list[dict]) -> dict:
    """Per (task, mode) stability + overall means."""
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r["task_id"], r["poison_mode"])].append(r)
    per_group = [
        summarize_stability_group(task_id=tid, poison_mode=mode, rows=rs)
        for (tid, mode), rs in sorted(groups.items())
    ]
    agree = [g["top1_agreement_vs_mode"] for g in per_group if g["top1_agreement_vs_mode"] is not None]
    pairwise = [
        g["top1_pairwise_agreement"] for g in per_group if g["top1_pairwise_agreement"] is not None
    ]
    taus = [
        g["mean_pairwise_kendall_tau"]
        for g in per_group
        if g["mean_pairwise_kendall_tau"] is not None
    ]
    return {
        "n_groups": len(per_group),
        "mean_top1_agreement_vs_mode": sum(agree) / len(agree) if agree else None,
        "mean_top1_pairwise_agreement": sum(pairwise) / len(pairwise) if pairwise else None,
        "mean_kendall_tau": sum(taus) / len(taus) if taus else None,
        "by_group": per_group,
        "volume_summary": aggregate(rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-runs", type=int, default=102, help="Total live runs (default 102)")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=None, help="Optional OpenAI seed")
    parser.add_argument(
        "--stoch-matrix",
        action="store_true",
        help="Run small temperature×seed matrix instead of --n-runs grid",
    )
    parser.add_argument(
        "--stability",
        action="store_true",
        help="Attribution Stability: K independent executions per task (Kendall τ + top-1)",
    )
    parser.add_argument(
        "--stability-reps",
        type=int,
        default=5,
        help="Independent executions per task for --stability (default 5)",
    )
    parser.add_argument(
        "--stability-mode",
        type=str,
        default="POISON_PLANNER",
        choices=[m.value for m in MODES],
        help="Poison mode for --stability (default POISON_PLANNER)",
    )
    parser.add_argument("--out", type=str, default="results/week5_live_langgraph.json")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        # load via credit_assignment.llm side effect
        import credit_assignment.llm  # noqa: F401

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY required for live runs")

    os.environ["USE_MOCK_LLM"] = "0"
    os.environ["FAIL_ON_LLM_ERROR"] = "1"
    tasks = load_tasks()
    rows: list[dict] = []
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    stability_summary = None

    if args.stability:
        mode = PoisonMode(args.stability_mode)
        # Independent executions: distinct seeds; temp from --temperature (default 0.0)
        # Use temp>0 when probing sampling noise; seeds still vary even at temp=0.
        total = len(tasks) * args.stability_reps
        print(
            f"Attribution Stability: {len(tasks)} tasks × {args.stability_reps} reps "
            f"mode={mode.value} temp={args.temperature} (n={total})"
        )
        run_idx = 0
        for task in tasks:
            for rep in range(args.stability_reps):
                seed = 1000 + run_idx  # distinct seed per execution
                print(
                    f"[{run_idx+1}/{total}] {task.task_id} rep={rep} seed={seed} ...",
                    flush=True,
                )
                row = run_one(
                    task=task,
                    mode=mode,
                    run_idx=run_idx,
                    temperature=args.temperature,
                    seed=seed,
                )
                row["stability_rep"] = rep
                rows.append(row)
                run_idx += 1
                if run_idx % 5 == 0 or run_idx == total:
                    stability_summary = aggregate_stability(rows)
                    out_path.write_text(
                        json.dumps(
                            {
                                "experiment": "week5_attribution_stability",
                                "partial": run_idx < total,
                                "summary": stability_summary,
                                "rows": rows,
                            },
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                    s = stability_summary
                    print(
                        f"  checkpoint top1_agree={s['mean_top1_agreement_vs_mode']} "
                        f"kendall={s['mean_kendall_tau']} "
                        f"scored={s['volume_summary']['n_scored']}/{s['volume_summary']['n_attempted']}",
                        flush=True,
                    )
    elif args.stoch_matrix:
        # Same task/mode; vary temperature and seed — stability of CR top-1
        task = tasks[0]
        mode = PoisonMode.POISON_PLANNER
        temps = [0.0, 0.3, 0.7]
        seeds = [None, 1, 2, 3]
        schedule_meta = []
        for temp in temps:
            for seed in seeds:
                schedule_meta.append((task, mode, temp, seed))
        print(f"Stochasticity matrix: {len(schedule_meta)} runs on {task.task_id}/{mode.value}")
        for i, (task, mode, temp, seed) in enumerate(schedule_meta):
            print(f"[{i+1}/{len(schedule_meta)}] temp={temp} seed={seed} ...", flush=True)
            row = run_one(task=task, mode=mode, run_idx=i, temperature=temp, seed=seed)
            rows.append(row)
            # incremental save
            out_path.write_text(
                json.dumps({"partial": True, "rows": rows}, indent=2), encoding="utf-8"
            )
    else:
        schedule = build_schedule(args.n_runs, tasks)
        print(f"Live LangGraph attribution: n_runs={args.n_runs} temp={args.temperature}")
        for task, mode, idx in schedule:
            print(f"[{idx+1}/{args.n_runs}] {mode.value} task={task.task_id} ...", flush=True)
            row = run_one(
                task=task,
                mode=mode,
                run_idx=idx,
                temperature=args.temperature,
                seed=args.seed,
            )
            rows.append(row)
            if (idx + 1) % 5 == 0 or idx + 1 == args.n_runs:
                summary = aggregate(rows)
                out_path.write_text(
                    json.dumps(
                        {
                            "experiment": "week5_live_langgraph",
                            "partial": idx + 1 < args.n_runs,
                            "summary": summary,
                            "rows": rows,
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                print(
                    f"  checkpoint CR P@1={summary['cr_p_at_1']:.3f} "
                    f"scored={summary['n_scored']}/{summary['n_attempted']} "
                    f"fails={summary['failure_counts_by_stage']}",
                    flush=True,
                )

    if args.stability:
        summary = stability_summary or aggregate_stability(rows)
        payload = {
            "experiment": "week5_attribution_stability",
            "claim_note": (
                "Attribution Stability appendix: K independent live executions per task. "
                "Reports top-1 agreement and mean pairwise Kendall τ. "
                "Not a repair result; not SWE-bench."
            ),
            "summary": summary,
            "rows": rows,
        }
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print("\n=== Attribution Stability ===")
        print(json.dumps({k: v for k, v in summary.items() if k != "by_group"}, indent=2))
        print("by_group:")
        for g in summary.get("by_group") or []:
            print(
                f"  {g['task_id']}: top1_agree={g['top1_agreement_vs_mode']} "
                f"kendall={g['mean_pairwise_kendall_tau']} top1s={g['top1s']}"
            )
        print(f"Wrote {out_path}")
        return

    summary = aggregate(rows)
    payload = {
        "experiment": "week5_live_langgraph" + ("_stoch" if args.stoch_matrix else ""),
        "claim_note": (
            "Live LLM traces — not offline recorded stubs. "
            "Still not SWE-bench/WebArena. Paper results require this tier."
        ),
        "summary": summary,
        "rows": rows,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("\n=== Live summary ===")
    print(json.dumps(summary, indent=2))
    print(f"gate={'PASS' if summary['week5_live_gate_pass'] else 'FAIL'}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
