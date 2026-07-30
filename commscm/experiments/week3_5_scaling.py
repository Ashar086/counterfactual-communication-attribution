"""
Week 3.5 — Scaling validation for COW Descendant Replay.

Produces the Replay Complexity Suite evidence package:
  - Runtime / evals / materialization vs N (fixed 10% descendant ratio)
  - vs descendant ratio (fixed N)
  - vs branching factor
  - vs shared subgraph density

Plus paper-ready plots aligning structural evals, materialized nodes, and wall-clock.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import matplotlib.pyplot as plt

from commscm.benchmarks.replay_complexity import ReplayComplexitySpec, build_replay_complexity_trace
from commscm.estimators.replay import (
    DescendantReplayEngine,
    FullReplayEngine,
    fault_marker_outcome,
)
from commscm.interventions.soft import SoftIntervention
from commscm.runtime.mechanisms import MechanismRegistry, descendants_of


# Structural work dominates; outcome kept cheap so fixed costs don't mask scaling.
STRUCTURAL_COST_ITERS = 3000
OUTCOME_COST_ITERS = 40
REPEATS = 3
SEED = 0

RESULTS_DIR = Path("results/week3_5")
FIG_DIR = RESULTS_DIR / "figures"


def _engines():
    kwargs = dict(
        structural_cost_iters=STRUCTURAL_COST_ITERS,
        outcome_cost_iters=OUTCOME_COST_ITERS,
    )
    return (
        FullReplayEngine(fault_marker_outcome, MechanismRegistry(), **kwargs),
        DescendantReplayEngine(fault_marker_outcome, MechanismRegistry(), **kwargs),
    )


def _measure(n: int, b: int, d: float, s: float, *, repeats: int = REPEATS) -> dict:
    tr = build_replay_complexity_trace(
        ReplayComplexitySpec(
            n_events=n,
            branching_factor=b,
            descendant_ratio=d,
            shared_subgraph_frac=s,
            seed=SEED,
        )
    )
    oracle, desc = _engines()
    intervention = SoftIntervention(event_id="E0", use_channel_null=True, tag="w35")
    n_desc = len(descendants_of(tr.dag, "E0"))

    o_totals, d_totals = [], []
    o_struct, d_struct = [], []
    o_mat_ms, d_mat_ms = [], []
    last_o = last_d = None
    for _ in range(repeats):
        r_o = oracle.replay(tr, intervention)
        r_d = desc.replay(tr, intervention)
        last_o, last_d = r_o, r_d
        o_totals.append(r_o.cost.total_ms)
        d_totals.append(r_d.cost.total_ms)
        o_struct.append(r_o.cost.structural_eval_ms)
        d_struct.append(r_d.cost.structural_eval_ms)
        o_mat_ms.append(r_o.cost.materialization_ms)
        d_mat_ms.append(r_d.cost.materialization_ms)

    assert last_o is not None and last_d is not None
    o_med = statistics.median(o_totals)
    d_med = statistics.median(d_totals)
    return {
        "n_events": n,
        "branching_factor": b,
        "descendant_ratio_target": d,
        "descendant_ratio_actual": tr.outcome.metrics["descendant_ratio_actual"],
        "shared_subgraph_frac": s,
        "n_descendants": n_desc,
        "affected_nodes": n_desc + 1,  # root + descendants
        "oracle_total_ms_median": round(o_med, 3),
        "descendant_total_ms_median": round(d_med, 3),
        "oracle_total_ms_all": [round(x, 3) for x in o_totals],
        "descendant_total_ms_all": [round(x, 3) for x in d_totals],
        "oracle_structural_ms_median": round(statistics.median(o_struct), 3),
        "descendant_structural_ms_median": round(statistics.median(d_struct), 3),
        "oracle_materialization_ms_median": round(statistics.median(o_mat_ms), 3),
        "descendant_materialization_ms_median": round(statistics.median(d_mat_ms), 3),
        "oracle_structural_evals": last_o.cost.structural_evals,
        "descendant_structural_evals": last_d.cost.structural_evals,
        "oracle_materialized_nodes": last_o.cost.materialized_nodes,
        "descendant_materialized_nodes": last_d.cost.materialized_nodes,
        "speedup_median": round((o_med / d_med) if d_med else 0.0, 3),
        "agreement": last_o.counterfactual_reward == last_d.counterfactual_reward,
    }


def sweep_n_fixed_ratio() -> list[dict]:
    """Primary scaling-law check: fix ratio=10%, vary N."""
    rows = []
    for n in (100, 250, 500, 1000, 2000):
        print(f"  N-scaling: n={n} ...", flush=True)
        rows.append(_measure(n, b=2, d=0.10, s=0.25))
    return rows


def sweep_descendant_ratio() -> list[dict]:
    rows = []
    for d in (0.1, 0.2, 0.4, 0.6, 0.8, 1.0):
        print(f"  ratio-scaling: d={d} ...", flush=True)
        rows.append(_measure(500, b=2, d=d, s=0.25))
    return rows


def sweep_branching() -> list[dict]:
    rows = []
    for b in (1, 2, 4, 8):
        print(f"  branching: b={b} ...", flush=True)
        rows.append(_measure(500, b=b, d=0.10, s=0.25))
    return rows


def sweep_shared() -> list[dict]:
    rows = []
    for s in (0.0, 0.25, 0.5, 0.75):
        print(f"  shared: s={s} ...", flush=True)
        rows.append(_measure(500, b=2, d=0.10, s=s))
    return rows


def _style():
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.grid": True,
            "grid.alpha": 0.25,
            "font.size": 11,
        }
    )


def plot_ratio_alignment(rows: list[dict], path: Path) -> None:
    """Structural evals, materialized nodes, wall-clock vs descendant ratio."""
    _style()
    ratios = [r["descendant_ratio_actual"] for r in rows]
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 3.6))

    axes[0].plot(ratios, [r["oracle_structural_evals"] for r in rows], "o-", label="Exact")
    axes[0].plot(ratios, [r["descendant_structural_evals"] for r in rows], "s-", label="COW Descendant")
    axes[0].set_xlabel("Descendant ratio")
    axes[0].set_ylabel("Structural evaluations")
    axes[0].set_title("Evals vs ratio")
    axes[0].legend(frameon=False)

    axes[1].plot(ratios, [r["oracle_materialized_nodes"] for r in rows], "o-", label="Exact")
    axes[1].plot(ratios, [r["descendant_materialized_nodes"] for r in rows], "s-", label="COW Descendant")
    axes[1].set_xlabel("Descendant ratio")
    axes[1].set_ylabel("Materialized nodes")
    axes[1].set_title("Materialization vs ratio")
    axes[1].legend(frameon=False)

    axes[2].plot(ratios, [r["oracle_total_ms_median"] for r in rows], "o-", label="Exact")
    axes[2].plot(ratios, [r["descendant_total_ms_median"] for r in rows], "s-", label="COW Descendant")
    axes[2].set_xlabel("Descendant ratio")
    axes[2].set_ylabel("Wall-clock (ms, median)")
    axes[2].set_title("Runtime vs ratio")
    axes[2].legend(frameon=False)

    fig.suptitle("N=500 — Descendant Replay (COW) scales with affected subgraph", y=1.02)
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def plot_n_scaling(rows: list[dict], path: Path) -> None:
    _style()
    ns = [r["n_events"] for r in rows]
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.6))

    axes[0].plot(ns, [r["oracle_total_ms_median"] for r in rows], "o-", label="Exact")
    axes[0].plot(ns, [r["descendant_total_ms_median"] for r in rows], "s-", label="COW Descendant")
    axes[0].set_xlabel("Trace length N")
    axes[0].set_ylabel("Wall-clock (ms, median)")
    axes[0].set_title("Runtime vs N (descendant ratio = 10%)")
    axes[0].legend(frameon=False)

    axes[1].plot(ns, [r["oracle_structural_evals"] for r in rows], "o-", label="Exact evals")
    axes[1].plot(ns, [r["descendant_structural_evals"] for r in rows], "s-", label="COW evals")
    axes[1].plot(ns, [r["descendant_materialized_nodes"] for r in rows], "^--", label="COW mat. nodes")
    axes[1].plot(ns, [r["affected_nodes"] for r in rows], ":", color="gray", label="|affected|")
    axes[1].set_xlabel("Trace length N")
    axes[1].set_ylabel("Count")
    axes[1].set_title("Complexity counts vs N")
    axes[1].legend(frameon=False)

    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def plot_axis(rows: list[dict], x_key: str, xlabel: str, title: str, path: Path) -> None:
    _style()
    xs = [r[x_key] for r in rows]
    fig, ax = plt.subplots(figsize=(5.2, 3.6))
    ax.plot(xs, [r["oracle_total_ms_median"] for r in rows], "o-", label="Exact")
    ax.plot(xs, [r["descendant_total_ms_median"] for r in rows], "s-", label="COW Descendant")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Wall-clock (ms, median)")
    ax.set_title(title)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def summarize(payload: dict) -> dict:
    """When does replay become expensive, and when do optimizations matter?"""
    n_rows = payload["n_scaling_fixed_10pct"]
    ratio_rows = payload["descendant_ratio_sweep"]

    # Growth: oracle vs COW from smallest to largest N
    n0, n1 = n_rows[0], n_rows[-1]
    oracle_growth = n1["oracle_total_ms_median"] / max(n0["oracle_total_ms_median"], 1e-9)
    cow_growth = n1["descendant_total_ms_median"] / max(n0["descendant_total_ms_median"], 1e-9)
    n_growth = n1["n_events"] / n0["n_events"]
    affected_growth = n1["affected_nodes"] / max(n0["affected_nodes"], 1)

    sparse = ratio_rows[0]
    dense = ratio_rows[-1]

    return {
        "scaling_law": {
            "statement": (
                "At fixed 10% descendant ratio, Exact Replay wall-clock grows roughly with N; "
                "COW Descendant grows with the affected subgraph (|affected| ~ 0.1N), not full N."
            ),
            "n_range": [n0["n_events"], n1["n_events"]],
            "n_fold": n_growth,
            "affected_fold": round(affected_growth, 3),
            "oracle_runtime_fold": round(oracle_growth, 3),
            "cow_runtime_fold": round(cow_growth, 3),
            "cow_evals_track_affected": all(
                r["descendant_structural_evals"] == r["n_descendants"]
                or r["descendant_structural_evals"] == r["affected_nodes"] - 1
                for r in n_rows
            ),
            "cow_materialization_tracks_affected": all(
                r["descendant_materialized_nodes"] == r["affected_nodes"] for r in n_rows
            ),
        },
        "when_expensive": {
            "exact_replay": "Costly whenever N is large and structural evaluations are expensive (LLM/tool-like), because both evals and materialization are O(N).",
            "dense_interventions": (
                f"As descendant ratio → 1 (here {dense['descendant_ratio_actual']}), "
                "COW converges to Exact Replay cost; optimizations matter less."
            ),
        },
        "when_optimizations_matter": {
            "sparse_interventions": (
                f"At ~10% affected (ratio={sparse['descendant_ratio_actual']}, N=500), "
                f"median wall-clock speedup ~{sparse['speedup_median']}x by restricting "
                "both structural evaluation and materialization to the affected subgraph."
            ),
            "claim_template": (
                "Under sparse interventions (~10% affected descendants), Copy-on-Write replay "
                "achieves approximately {speedup}x wall-clock speedup by restricting both "
                "structural evaluation and graph materialization to the affected subgraph. "
                "As the affected ratio approaches one, replay converges to Exact Replay, as expected."
            ).format(speedup=sparse["speedup_median"]),
        },
        "complexity_table": {
            "Exact Replay": {"structural_evals": "O(N)", "materialization": "O(N)"},
            "Descendant (pre-COW)": {
                "structural_evals": "O(|affected|)",
                "materialization": "O(N)",
            },
            "Descendant (COW)": {
                "structural_evals": "O(|affected|)",
                "materialization": "O(|affected|)",
            },
        },
    }


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    print("Week 3.5 — Replay Complexity scaling validation")
    print("=" * 60)

    payload = {
        "experiment": "week3_5_scaling_validation",
        "suite": (
            "Replay Complexity Suite: a synthetic benchmark generator that independently "
            "controls trace length, branching factor, descendant ratio, and shared subgraph "
            "density to isolate replay complexity."
        ),
        "structural_cost_iters": STRUCTURAL_COST_ITERS,
        "outcome_cost_iters": OUTCOME_COST_ITERS,
        "repeats": REPEATS,
        "n_scaling_fixed_10pct": sweep_n_fixed_ratio(),
        "descendant_ratio_sweep": sweep_descendant_ratio(),
        "branching_sweep": sweep_branching(),
        "shared_subgraph_sweep": sweep_shared(),
    }
    payload["summary"] = summarize(payload)

    out = RESULTS_DIR / "scaling_validation.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")

    plot_n_scaling(payload["n_scaling_fixed_10pct"], FIG_DIR / "runtime_vs_n.png")
    plot_ratio_alignment(payload["descendant_ratio_sweep"], FIG_DIR / "alignment_vs_ratio.png")
    plot_axis(
        payload["branching_sweep"],
        "branching_factor",
        "Branching factor",
        "Runtime vs branching (N=500, ratio=10%)",
        FIG_DIR / "runtime_vs_branching.png",
    )
    plot_axis(
        payload["shared_subgraph_sweep"],
        "shared_subgraph_frac",
        "Shared subgraph fraction",
        "Runtime vs shared density (N=500, ratio=10%)",
        FIG_DIR / "runtime_vs_shared.png",
    )
    print(f"Wrote figures under {FIG_DIR}")

    s = payload["summary"]
    print("\n--- Summary ---")
    print(s["scaling_law"]["statement"])
    print(
        f"N fold={s['scaling_law']['n_fold']:.1f}, "
        f"oracle runtime fold={s['scaling_law']['oracle_runtime_fold']:.2f}, "
        f"COW runtime fold={s['scaling_law']['cow_runtime_fold']:.2f}, "
        f"affected fold={s['scaling_law']['affected_fold']:.2f}"
    )
    print(s["when_optimizations_matter"]["claim_template"])

    # Console tables
    print("\nN-scaling @ 10% descendants")
    print(f"{'N':>6} {'|A|':>6} {'O_ms':>8} {'D_ms':>8} {'spd':>6} {'evalsD':>7} {'matD':>6}")
    for r in payload["n_scaling_fixed_10pct"]:
        print(
            f"{r['n_events']:6d} {r['affected_nodes']:6d} "
            f"{r['oracle_total_ms_median']:8.1f} {r['descendant_total_ms_median']:8.1f} "
            f"{r['speedup_median']:6.2f} {r['descendant_structural_evals']:7d} "
            f"{r['descendant_materialized_nodes']:6d}"
        )


if __name__ == "__main__":
    main()
