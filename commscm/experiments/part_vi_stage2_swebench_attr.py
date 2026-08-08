"""
Part VI Stage 2 — Attribution only on SWE-bench Verified–shaped (no repair).

Metrics: P@1, MRR, Gold Hit, Attribution Stability. Frozen CR; adapter-only.
"""

from __future__ import annotations

import argparse
import json
import os
import traceback
from pathlib import Path

from credit_assignment import llm as _llm  # noqa: F401
from credit_assignment.fault_injection import FaultInjector, PoisonMode
from commscm.adapters.swebench.extract import swebench_reward_outcome, swebench_state_to_run_trace
from commscm.adapters.swebench.load import load_swebench_verified_subset, offline_fixture_instances
from commscm.adapters.swebench.mechanisms import make_swebench_sticky_registry
from commscm.adapters.swebench.pipeline import run_swebench_pipeline
from commscm.attribution.subset import SubsetAttributionEngine
from commscm.estimators.replay import DescendantReplayEngine
from commscm.metrics.ranking_stability import summarize_stability_group

AGENT_EVENTS = {"C1", "C2", "C3", "C4", "C5"}
MODES = (PoisonMode.POISON_PLANNER, PoisonMode.POISON_CODER, PoisonMode.POISON_REVIEWER)


def score_trace(tr):
    mechs = make_swebench_sticky_registry(tr.dag)
    return SubsetAttributionEngine(
        DescendantReplayEngine(swebench_reward_outcome, mechs, structural_cost_iters=0),
        AGENT_EVENTS,
        name="SWEBenchCR",
    ).score(tr)


def _mrr(ranking: list[str], gold: str | None) -> float:
    if not gold or gold not in ranking:
        return 0.0
    return 1.0 / (ranking.index(gold) + 1)


def _reward_only_top1(rows: list) -> str | None:
    if not rows:
        return None
    return sorted(rows, key=lambda r: r.event_id, reverse=True)[0].event_id


def _random_top1(rows: list, seed: int) -> str | None:
    import random

    ids = [r.event_id for r in rows]
    return random.Random(seed).choice(ids) if ids else None


def load_instances(n: int):
    try:
        return load_swebench_verified_subset(n=n, seed=42), "huggingface"
    except Exception as exc:  # noqa: BLE001
        print(f"HF load failed ({exc}); offline fixtures")
        return offline_fixture_instances(min(n, 3)), "offline_fixture"


def run_one(*, instance, mode: PoisonMode, run_idx: int) -> dict:
    row: dict = {
        "run_idx": run_idx,
        "instance_id": instance.instance_id,
        "task_id": instance.instance_id,
        "poison_mode": mode.value,
        "framework": "swebench_shaped",
        "pipeline_ok": False,
        "extract_ok": False,
        "attribution_ok": False,
        "failures": [],
    }
    try:
        state = run_swebench_pipeline(
            instance,
            fault_injector=FaultInjector(mode=mode),
        )
        row["pipeline_ok"] = True
        row["global_reward"] = float(state.global_reward)
        row["poisoned_node"] = state.poisoned_node
    except Exception as exc:  # noqa: BLE001
        row["failures"].append({"stage": "pipeline", "error": f"{type(exc).__name__}: {exc}"})
        row["traceback"] = traceback.format_exc()[-1500:]
        return row

    try:
        tr = swebench_state_to_run_trace(
            state,
            run_id=f"swe2_{run_idx}_{mode.value}_{instance.instance_id}",
            task_id=instance.instance_id,
        )
        row["extract_ok"] = True
        row["gold"] = tr.gold_fault_event_id
        row["n_events"] = len(tr.dag.events)
    except Exception as exc:  # noqa: BLE001
        row["failures"].append({"stage": "extract", "error": f"{type(exc).__name__}: {exc}"})
        return row

    try:
        report = score_trace(tr)
        ordered = sorted(report.rows, key=lambda r: (-r.delta_y, r.event_id))
        ranking = [r.event_id for r in ordered]
        row["attribution_ok"] = True
        row["cr_top1"] = report.predicted_top1
        row["cr_ranking"] = ranking
        row["reward_only_top1"] = _reward_only_top1(report.rows)
        row["random_top1"] = _random_top1(report.rows, seed=run_idx)
        row["cr_hit"] = report.predicted_top1 == tr.gold_fault_event_id
        row["gold_hit"] = row["cr_hit"]
        row["reward_only_hit"] = row["reward_only_top1"] == tr.gold_fault_event_id
        row["random_hit"] = row["random_top1"] == tr.gold_fault_event_id
        row["mrr"] = _mrr(ranking, tr.gold_fault_event_id)
    except Exception as exc:  # noqa: BLE001
        row["failures"].append(
            {"stage": "attribution", "error": f"{type(exc).__name__}: {exc}"}
        )
        row["traceback"] = traceback.format_exc()[-1500:]
    return row


def aggregate(rows: list[dict]) -> dict:
    scored = [r for r in rows if r.get("attribution_ok")]
    n = len(scored)

    def rate(key: str) -> float:
        return sum(1 for r in scored if r.get(key)) / n if n else 0.0

    by_mode: dict[str, dict] = {}
    for mode in MODES:
        subset = [r for r in scored if r["poison_mode"] == mode.value]
        m = len(subset)
        by_mode[mode.value] = {
            "n": m,
            "cr_p_at_1": sum(1 for r in subset if r.get("cr_hit")) / m if m else 0.0,
            "mrr": sum(float(r.get("mrr") or 0.0) for r in subset) / m if m else 0.0,
            "reward_only_p_at_1": (
                sum(1 for r in subset if r.get("reward_only_hit")) / m if m else 0.0
            ),
            "random_p_at_1": sum(1 for r in subset if r.get("random_hit")) / m if m else 0.0,
        }

    return {
        "n_attempted": len(rows),
        "n_scored": n,
        "pipeline_ok_rate": sum(1 for r in rows if r.get("pipeline_ok")) / len(rows) if rows else 0.0,
        "extract_ok_rate": sum(1 for r in rows if r.get("extract_ok")) / len(rows) if rows else 0.0,
        "attribution_ok_rate": n / len(rows) if rows else 0.0,
        "cr_p_at_1": rate("cr_hit"),
        "gold_hit_rate": rate("gold_hit"),
        "mrr": sum(float(r.get("mrr") or 0.0) for r in scored) / n if n else 0.0,
        "reward_only_p_at_1": rate("reward_only_hit"),
        "random_p_at_1": rate("random_hit"),
        "by_poison_mode": by_mode,
        "stage2_gate_pass": (
            n > 0 and rate("cr_hit") > rate("reward_only_hit") and rate("cr_hit") > rate("random_hit")
        ),
        "core_unchanged": True,
    }


def build_schedule(n_runs: int, instances: list) -> list:
    schedule = []
    i = 0
    while len(schedule) < n_runs:
        inst = instances[i % len(instances)]
        mode = MODES[i % len(MODES)]
        schedule.append((inst, mode, len(schedule)))
        i += 1
    return schedule


def run_stability(instances: list, *, reps: int, mode: PoisonMode) -> dict:
    rows: list[dict] = []
    for inst in instances[:2]:
        for rep in range(reps):
            row = run_one(instance=inst, mode=mode, run_idx=10_000 + rep)
            row["stability_rep"] = rep
            rows.append(row)
    groups = []
    by_key: dict[tuple[str, str], list] = {}
    for r in rows:
        if not r.get("attribution_ok"):
            continue
        key = (r["task_id"], r["poison_mode"])
        by_key.setdefault(key, []).append(r)
    for (tid, pm), rs in by_key.items():
        groups.append(summarize_stability_group(task_id=tid, poison_mode=pm, rows=rs))
    taus = [
        g["mean_pairwise_kendall_tau"]
        for g in groups
        if g.get("mean_pairwise_kendall_tau") is not None
    ]
    agrees = [
        g["top1_agreement_vs_mode"]
        for g in groups
        if g.get("top1_agreement_vs_mode") is not None
    ]
    return {
        "n_rows": len(rows),
        "groups": groups,
        "mean_kendall_tau": sum(taus) / len(taus) if taus else None,
        "mean_top1_modal_agreement": sum(agrees) / len(agrees) if agrees else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-runs", type=int, default=24)
    parser.add_argument("--n-instances", type=int, default=8)
    parser.add_argument("--stability-reps", type=int, default=3)
    parser.add_argument("--skip-stability", action="store_true")
    parser.add_argument("--out", type=str, default="results/part_vi_stage2_swebench_attr.json")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY required")
    os.environ["USE_MOCK_LLM"] = "0"
    os.environ["FAIL_ON_LLM_ERROR"] = "1"

    instances, source = load_instances(args.n_instances)
    rows: list[dict] = []
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    schedule = build_schedule(args.n_runs, instances)
    print(f"Part VI Stage 2 SWE-bench attribution: n_runs={args.n_runs} source={source}")
    print("Core Invariance: adapter-only; no Part I–III changes. No repair.")

    for inst, mode, idx in schedule:
        print(f"[{idx+1}/{args.n_runs}] {mode.value} {inst.instance_id} ...", flush=True)
        row = run_one(instance=inst, mode=mode, run_idx=idx)
        rows.append(row)
        print(
            f"  cr_top1={row.get('cr_top1')} gold={row.get('gold')} "
            f"hit={row.get('cr_hit')} mrr={row.get('mrr')} y={row.get('global_reward')}",
            flush=True,
        )
        if (idx + 1) % 4 == 0 or idx + 1 == args.n_runs:
            summary = aggregate(rows)
            out_path.write_text(
                json.dumps(
                    {
                        "experiment": "part_vi_stage2_swebench_attribution",
                        "partial": True,
                        "instance_source": source,
                        "summary": summary,
                        "rows": rows,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(
                f"  checkpoint CR P@1={summary['cr_p_at_1']:.3f} MRR={summary['mrr']:.3f}",
                flush=True,
            )

    stability = None
    if not args.skip_stability and args.stability_reps > 0:
        print(f"\nAttribution stability: 2 instances × {args.stability_reps} reps ...", flush=True)
        stability = run_stability(
            instances, reps=args.stability_reps, mode=PoisonMode.POISON_PLANNER
        )
        print(
            f"  kendall={stability.get('mean_kendall_tau')} "
            f"top1_agree={stability.get('mean_top1_modal_agreement')}",
            flush=True,
        )

    summary = aggregate(rows)
    payload = {
        "experiment": "part_vi_stage2_swebench_attribution",
        "hypothesis": "H_part_vi frozen CR attributes on SWE-bench Verified–shaped",
        "claim_note": (
            "Attribution only — no repair. SWE-bench Verified–shaped (not Docker resolve@1). "
            "Core Invariance Principle: adapter-only."
        ),
        "instance_source": source,
        "instance_ids": [i.instance_id for i in instances],
        "summary": summary,
        "attribution_stability": stability,
        "rows": rows,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("\n=== Stage 2 summary ===")
    print(json.dumps(summary, indent=2))
    print(f"gate={'PASS' if summary['stage2_gate_pass'] else 'FAIL'}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
