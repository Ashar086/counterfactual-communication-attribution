"""Profile Exact / Descendant(COW) / Cached cost components."""

from __future__ import annotations

import json
from pathlib import Path

from commscm.benchmarks.replay_complexity import ReplayComplexitySpec, build_replay_complexity_trace
from commscm.estimators.replay import (
    CachedDescendantReplayEngine,
    CostBreakdown,
    DescendantReplayEngine,
    FullReplayEngine,
    fault_marker_outcome,
)
from commscm.interventions.soft import SoftIntervention
from commscm.runtime.mechanisms import MechanismRegistry


STRUCTURAL_COST_ITERS = 5000
OUTCOME_COST_ITERS = 50


def _engines():
    kwargs = dict(
        structural_cost_iters=STRUCTURAL_COST_ITERS,
        outcome_cost_iters=OUTCOME_COST_ITERS,
    )
    return {
        "Oracle": FullReplayEngine(fault_marker_outcome, MechanismRegistry(), **kwargs),
        "Descendant": DescendantReplayEngine(fault_marker_outcome, MechanismRegistry(), **kwargs),
        "Cached": CachedDescendantReplayEngine(fault_marker_outcome, MechanismRegistry(), **kwargs),
    }


def _row(name: str, cost: CostBreakdown) -> dict:
    return {
        "estimator": name,
        "intervention_ms": cost.intervention_ms,
        "replay_ms": cost.replay_ms,
        "structural_eval_ms": cost.structural_eval_ms,
        "materialization_ms": cost.materialization_ms,
        "evaluation_ms": cost.evaluation_ms,
        "cache_ms": cost.cache_ms,
        "total_ms": cost.total_ms,
        "structural_evals": cost.structural_evals,
        "materialized_nodes": cost.materialized_nodes,
        "cache_hits": cost.cache_hits,
        "cache_misses": cost.cache_misses,
    }


def main() -> None:
    trace = build_replay_complexity_trace(
        ReplayComplexitySpec(
            n_events=250,
            branching_factor=4,
            descendant_ratio=0.4,
            shared_subgraph_frac=0.25,
            seed=0,
        )
    )
    root = "E0"
    intervention = SoftIntervention(event_id=root, use_channel_null=True, tag="profile")
    engines = _engines()

    rows = []
    print("Component cost table (single intervention on E0) — after COW descendant replay")
    print(
        f"{'Estimator':<12} {'Struct':>8} {'Mat':>8} {'Eval':>8} {'Cache':>8} "
        f"{'Total':>8} {'#evals':>7} {'#nodes':>7}"
    )
    print("-" * 78)
    for name, eng in engines.items():
        result = eng.replay(trace, intervention)
        row = _row(name, result.cost)
        rows.append(row)
        print(
            f"{name:<12} {row['structural_eval_ms']:8.2f} {row['materialization_ms']:8.2f} "
            f"{row['evaluation_ms']:8.2f} {row['cache_ms']:8.2f} {row['total_ms']:8.2f} "
            f"{row['structural_evals']:7d} {row['materialized_nodes']:7d}"
        )

    cached = engines["Cached"]
    warm = cached.replay(trace, intervention)
    warm_row = _row("Cached(warm)", warm.cost)
    rows.append(warm_row)
    print(
        f"{'Cached(warm)':<12} {warm_row['structural_eval_ms']:8.2f} {warm_row['materialization_ms']:8.2f} "
        f"{warm_row['evaluation_ms']:8.2f} {warm_row['cache_ms']:8.2f} {warm_row['total_ms']:8.2f} "
        f"{warm_row['structural_evals']:7d} {warm_row['materialized_nodes']:7d}"
    )
    print(
        "\nNote: Cached(warm) is a repeated-attribution / multi-intervention workload, "
        "not a general single-shot runtime claim."
    )

    out = {
        "objective": "Construct benchmarks that isolate the computational bottlenecks of exact replay.",
        "suite": "Replay Complexity Suite",
        "trace": trace.run_id,
        "metrics": dict(trace.outcome.metrics),
        "structural_cost_iters": STRUCTURAL_COST_ITERS,
        "outcome_cost_iters": OUTCOME_COST_ITERS,
        "paper_figure_hint": {
            "ExactReplay": ["Structural evaluations", "DAG materialization O(N)", "Replay bookkeeping"],
            "DescendantReplay_pre_COW": [
                "Fewer structural evaluations",
                "Same DAG materialization O(N)",
            ],
            "DescendantReplay_COW": [
                "Fewer structural evaluations",
                "Subgraph-only materialization O(|affected|)",
            ],
        },
        "rows": rows,
    }
    path = Path("results/week3_cost_profile.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
