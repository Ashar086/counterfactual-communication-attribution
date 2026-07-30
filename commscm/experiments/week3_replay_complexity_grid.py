"""Replay Complexity grid: runtime vs length / branching / descendant ratio / sharing."""

from __future__ import annotations

import json
from pathlib import Path

from commscm.benchmarks.replay_complexity import ReplayComplexitySpec, build_replay_complexity_trace
from commscm.estimators.replay import (
    DescendantReplayEngine,
    FullReplayEngine,
    fault_marker_outcome,
)
from commscm.interventions.soft import SoftIntervention
from commscm.runtime.mechanisms import MechanismRegistry


STRUCTURAL_COST_ITERS = 4000
OUTCOME_COST_ITERS = 50


def _measure(n: int, b: int, d: float, s: float) -> dict:
    tr = build_replay_complexity_trace(
        ReplayComplexitySpec(
            n_events=n,
            branching_factor=b,
            descendant_ratio=d,
            shared_subgraph_frac=s,
            seed=0,
        )
    )
    kwargs = dict(
        structural_cost_iters=STRUCTURAL_COST_ITERS,
        outcome_cost_iters=OUTCOME_COST_ITERS,
    )
    oracle = FullReplayEngine(fault_marker_outcome, MechanismRegistry(), **kwargs)
    desc = DescendantReplayEngine(fault_marker_outcome, MechanismRegistry(), **kwargs)
    intervention = SoftIntervention(event_id="E0", use_channel_null=True, tag="grid")
    r_o = oracle.replay(tr, intervention)
    r_d = desc.replay(tr, intervention)
    return {
        "n_events": n,
        "branching_factor": b,
        "descendant_ratio": d,
        "shared_subgraph_frac": s,
        "n_descendants": tr.outcome.metrics["n_descendants"],
        "oracle_total_ms": r_o.cost.total_ms,
        "descendant_total_ms": r_d.cost.total_ms,
        "oracle_structural_evals": r_o.cost.structural_evals,
        "descendant_structural_evals": r_d.cost.structural_evals,
        "oracle_materialized_nodes": r_o.cost.materialized_nodes,
        "descendant_materialized_nodes": r_d.cost.materialized_nodes,
        "oracle_materialization_ms": r_o.cost.materialization_ms,
        "descendant_materialization_ms": r_d.cost.materialization_ms,
        "speedup": round(
            (r_o.cost.total_ms / r_d.cost.total_ms) if r_d.cost.total_ms else 0.0, 3
        ),
        "agreement": r_o.counterfactual_reward == r_d.counterfactual_reward,
    }


def main() -> None:
    rows: list[dict] = []
    for n in (50, 100, 250, 500):
        rows.append(_measure(n, 2, 0.4, 0.25))
    for b in (1, 2, 4, 8):
        rows.append(_measure(250, b, 0.4, 0.25))
    for d in (0.1, 0.3, 0.6, 0.9):
        rows.append(_measure(250, 2, d, 0.25))
    for s in (0.0, 0.25, 0.5, 0.75):
        rows.append(_measure(250, 2, 0.6, s))

    print(
        f"{'n':>5} {'b':>3} {'d':>5} {'s':>5} {'O_ms':>8} {'D_ms':>8} "
        f"{'spd':>6} {'matD':>6} {'evalsD':>7}"
    )
    print("-" * 70)
    for r in rows:
        print(
            f"{r['n_events']:5d} {r['branching_factor']:3d} {r['descendant_ratio']:5.2f} "
            f"{r['shared_subgraph_frac']:5.2f} {r['oracle_total_ms']:8.2f} "
            f"{r['descendant_total_ms']:8.2f} {r['speedup']:6.2f} "
            f"{r['descendant_materialized_nodes']:6d} {r['descendant_structural_evals']:7d}"
        )

    out = {
        "experiment": "replay_complexity_grid_subsample_cow",
        "suite": "Replay Complexity Suite",
        "structural_cost_iters": STRUCTURAL_COST_ITERS,
        "note": (
            "Axis-isolating subsample. Design around branching / descendant ratio / "
            "shared subgraphs, not merely larger K."
        ),
        "rows": rows,
    }
    path = Path("results/week3_replay_complexity_grid.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    # Keep legacy filename as a copy pointer for old links
    Path("results/week3_bottleneck_grid.json").write_text(
        json.dumps({"deprecated": True, "see": "week3_replay_complexity_grid.json", **out}, indent=2),
        encoding="utf-8",
    )
    print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
