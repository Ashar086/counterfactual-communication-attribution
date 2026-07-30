"""
Week 4 Phase D / H2-lite: iterative CCAS on multi-path faults.

Compares CR-guided vs reward-only vs random under a fixed edit budget.
No GPTSwarm/AgentPrune bakeoff yet — isolates whether attribution helps search.
"""

from __future__ import annotations

import json
from pathlib import Path

from commscm.benchmarks.week4_multipath import build_multipath_fault_dataset
from commscm.ccas.loop import CCASLoop, make_operator


def _aggregate(results: list) -> dict:
    n = len(results)
    if n == 0:
        return {}
    successes = [r for r in results if r.success]
    return {
        "n": n,
        "success_rate": sum(1 for r in results if r.success) / n,
        "success_at_1": sum(1 for r in results if r.success and r.n_edits <= 1) / n,
        "success_at_2": sum(1 for r in results if r.success and r.n_edits <= 2) / n,
        "mean_edits_all": sum(r.n_edits for r in results) / n,
        "mean_edits_on_success": (
            sum(r.n_edits for r in successes) / len(successes) if successes else None
        ),
        "mean_gold_edges_hit": sum(r.gold_edges_hit for r in results) / n,
        "mean_y_final": sum(r.y_final for r in results) / n,
    }


def main() -> None:
    traces = build_multipath_fault_dataset(n_traces=30, branch_len=3, seed=0)
    budget = 4
    methods = ("random", "reward_only", "cr_guided")
    summary = {}
    examples = {}

    print("Phase D / H2-lite — iterative CCAS on multi-path faults")
    print(f"Traces={len(traces)} branch_len=3 edit_budget={budget}")
    print(
        f"{'Method':<14} {'succ':>6} {'@2':>6} {'edits':>7} {'edits|ok':>8} {'goldHit':>8}"
    )
    print("-" * 60)

    for method in methods:
        results = []
        for i, tr in enumerate(traces):
            op = make_operator(method, seed=i)
            loop = CCASLoop(op, edit_budget=budget)
            results.append(loop.run(tr))
        agg = _aggregate(results)
        summary[method] = agg
        examples[method] = [r.model_dump(mode="json") for r in results[:2]]
        edits_ok = agg["mean_edits_on_success"]
        edits_ok_s = f"{edits_ok:.3f}" if edits_ok is not None else "n/a"
        print(
            f"{method:<14} {agg['success_rate']:6.3f} {agg['success_at_2']:6.3f} "
            f"{agg['mean_edits_all']:7.3f} {edits_ok_s:>8} {agg['mean_gold_edges_hit']:8.3f}"
        )

    cr, rw, rd = summary["cr_guided"], summary["reward_only"], summary["random"]
    # H2-lite gate: CR succeeds at least as often, and uses fewer edits on average
    # among successes (or fewer edits overall when success rates are comparable).
    h2_pass = (
        cr["success_rate"] >= rw["success_rate"]
        and cr["success_rate"] >= rd["success_rate"]
        and cr["success_at_2"] >= rw["success_at_2"]
        and cr["success_at_2"] >= rd["success_at_2"]
        and (
            (cr["mean_edits_on_success"] is not None and rw["mean_edits_on_success"] is not None
             and cr["mean_edits_on_success"] <= rw["mean_edits_on_success"])
            or cr["mean_edits_all"] < rw["mean_edits_all"]
        )
        and cr["mean_gold_edges_hit"] >= rw["mean_gold_edges_hit"]
        and cr["mean_gold_edges_hit"] >= rd["mean_gold_edges_hit"]
    )
    verdict = {
        "h2_lite_pass": h2_pass,
        "rule": (
            "CR-guided must match/beat reward-only and random on success_rate and "
            "success_at_2, use fewer or equal edits on success, and hit more gold edges."
        ),
    }
    print("\nH2-lite gate:", "PASS" if h2_pass else "FAIL")
    print(verdict)

    out = {
        "experiment": "week4_phase_d_h2_lite",
        "phase": "D",
        "suite": "multipath_fault",
        "edit_budget": budget,
        "summary": summary,
        "examples": examples,
        "verdict": verdict,
    }
    path = Path("results/week4_phase_d.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
