"""
Week 4 Phase A/C — H1: harmful pathway identification.

Compare Random vs Reward-only vs CR-guided ArchitectureOperators.
No graph mutation. No iterative CCAS.
"""

from __future__ import annotations

import json
from pathlib import Path

from commscm.attribution.engines import DescendantReplayEstimator
from commscm.benchmarks.week3_random import build_random_dataset
from commscm.ccas.operators import (
    CRGuidedOperator,
    RandomOperator,
    RewardOnlyOperator,
    gold_harmful_edges,
)
from commscm.eval.h1_edges import aggregate_h1, score_proposal
from commscm.estimators.replay import DescendantReplayEngine, fault_marker_outcome
from commscm.runtime.mechanisms import MechanismRegistry


def main() -> None:
    traces = build_random_dataset(n_traces=60, n_events=20, seed=42)
    # Attribution for CR-guided only (COW descendant; Part II frozen).
    attr = DescendantReplayEstimator(
        DescendantReplayEngine(fault_marker_outcome, MechanismRegistry(), structural_cost_iters=0)
    )
    operators = {
        "random": RandomOperator(seed=0),
        "reward_only": RewardOnlyOperator(),
        "cr_guided": CRGuidedOperator(),
    }

    per_method: dict[str, list[dict]] = {m: [] for m in operators}
    for tr in traces:
        gold = gold_harmful_edges(tr)
        if not gold:
            continue
        report = attr.score(tr)
        for name, op in operators.items():
            prop = op.propose(tr, report)
            scored = score_proposal(prop, gold, ks=(1, 3, 5))
            scored["run_id"] = tr.run_id
            scored["n_gold_edges"] = len(gold)
            per_method[name].append(scored)

    summary = {}
    print("H1 — Harmful edge localization (Phase A proposals only)")
    print(f"{'Method':<14} {'P@1':>6} {'R@3':>6} {'nDCG@3':>8} {'FP@1':>6} {'n':>4}")
    print("-" * 52)
    for name, rows in per_method.items():
        m = aggregate_h1(rows, ks=(1, 3, 5))
        summary[name] = m.model_dump(mode="json")
        print(
            f"{name:<14} {m.precision_at_1:6.3f} {m.recall_at_k[3]:6.3f} "
            f"{m.ndcg_at_k[3]:8.3f} {m.false_positive_edit_rate:6.3f} {m.n:4d}"
        )

    cr = summary["cr_guided"]["precision_at_1"]
    rw = summary["reward_only"]["precision_at_1"]
    rd = summary["random"]["precision_at_1"]
    h1_pass = cr > rw and cr > rd
    verdict = {
        "h1_pass": h1_pass,
        "rule": (
            "CR-guided P@1 must strictly exceed reward-only and random before Phase D. "
            "Reward-only must not use FAULT_ label leakage."
        ),
        "cr_guided_p_at_1": cr,
        "reward_only_p_at_1": rw,
        "random_p_at_1": rd,
    }
    print("\nH1 gate:", "PASS" if h1_pass else "FAIL", verdict)

    out = {
        "experiment": "week4_h1_phase_a",
        "phase": "A",
        "mutation": False,
        "summary": summary,
        "verdict": verdict,
    }
    path = Path("results/week4_h1.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
