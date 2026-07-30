"""
Fixed-N descendant-ratio scaling (primary Week-3 claim), after COW materialization.

Claim (careful wording):
  Descendant Replay reduces structural evaluations in proportion to the affected
  subgraph; with copy-on-write materialization, wall-clock should track that
  reduction more closely than under full O(N) counterfactual DAG copies.
"""

from __future__ import annotations

import json
from pathlib import Path

from commscm.benchmarks.replay_complexity import build_descendant_ratio_suite
from commscm.estimators.replay import (
    CachedDescendantReplayEngine,
    DescendantReplayEngine,
    FullReplayEngine,
    fault_marker_outcome,
)
from commscm.interventions.soft import SoftIntervention
from commscm.runtime.mechanisms import MechanismRegistry, descendants_of


# Structural work dominates (LLM/tool-like); keep outcome cheap so fixed O(N)
# evaluation does not mask subgraph scaling.
STRUCTURAL_COST_ITERS = 5000
OUTCOME_COST_ITERS = 50
N_EVENTS = 500
RATIOS = [0.1, 0.2, 0.4, 0.6, 0.8, 1.0]


def main() -> None:
    traces = build_descendant_ratio_suite(
        n_events=N_EVENTS,
        branching_factor=2,
        ratios=RATIOS,
        shared_subgraph_frac=0.25,
        seed=0,
    )
    kwargs = dict(
        structural_cost_iters=STRUCTURAL_COST_ITERS,
        outcome_cost_iters=OUTCOME_COST_ITERS,
    )
    oracle = FullReplayEngine(fault_marker_outcome, MechanismRegistry(), **kwargs)
    desc = DescendantReplayEngine(fault_marker_outcome, MechanismRegistry(), **kwargs)
    cached = CachedDescendantReplayEngine(fault_marker_outcome, MechanismRegistry(), **kwargs)

    rows = []
    print(f"Fixed N={N_EVENTS}: COW Descendant vs Oracle (single intervention on E0)")
    print(
        f"{'ratio':>6} {'n_desc':>7} {'O_ms':>8} {'D_ms':>8} {'spd':>6} "
        f"{'evalsO':>7} {'evalsD':>7} {'matO':>6} {'matD':>6}"
    )
    print("-" * 90)

    for tr in traces:
        intervention = SoftIntervention(event_id="E0", use_channel_null=True, tag="ratio")
        n_desc = len(descendants_of(tr.dag, "E0"))
        ratio = float(tr.outcome.metrics["descendant_ratio_actual"])

        r_o = oracle.replay(tr, intervention)
        r_d = desc.replay(tr, intervention)
        r_c = cached.replay(tr, intervention)

        speedup = (r_o.cost.total_ms / r_d.cost.total_ms) if r_d.cost.total_ms else 0.0
        row = {
            "descendant_ratio_target": tr.outcome.metrics["descendant_ratio_target"],
            "descendant_ratio_actual": ratio,
            "n_descendants": n_desc,
            "n_events": N_EVENTS,
            "oracle": r_o.cost.model_dump(mode="json"),
            "descendant": r_d.cost.model_dump(mode="json"),
            "cached_cold": r_c.cost.model_dump(mode="json"),
            "speedup_descendant_vs_oracle": round(speedup, 3),
            "agreement_reward": r_o.counterfactual_reward == r_d.counterfactual_reward,
            "materialization_mode_descendant": r_d.materialization_mode,
        }
        rows.append(row)
        print(
            f"{ratio:6.2f} {n_desc:7d} {r_o.cost.total_ms:8.2f} {r_d.cost.total_ms:8.2f} "
            f"{speedup:6.2f} {r_o.cost.structural_evals:7d} {r_d.cost.structural_evals:7d} "
            f"{r_o.cost.materialized_nodes:6d} {r_d.cost.materialized_nodes:6d}"
        )

    out = {
        "experiment": "fixed_n_descendant_ratio_scaling_cow",
        "n_events": N_EVENTS,
        "structural_cost_iters": STRUCTURAL_COST_ITERS,
        "outcome_cost_iters": OUTCOME_COST_ITERS,
        "claim": (
            "Descendant Replay reduces structural evaluations in proportion to the "
            "affected subgraph; COW materialization should align wall-clock with that reduction."
        ),
        "avoid_overclaim": (
            "Do not state a blanket 'Descendant is K× faster'; report eval scaling "
            "and materialization scaling separately."
        ),
        "rows": rows,
    }
    path = Path("results/week3_descendant_ratio.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
