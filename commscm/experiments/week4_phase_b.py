"""
Week 4 Phase B — apply a single top-1 architecture edit; measure repair.

Uses a chain-fault suite where one harmful edge lies on the unique path to the
sink, so a correct single edit can recover the task proxy.
"""

from __future__ import annotations

import json
from pathlib import Path

from commscm.attribution.engines import DescendantReplayEstimator
from commscm.benchmarks.week4_chain import build_chain_fault_dataset
from commscm.ccas.apply_edit import ArchitectureRegistry, apply_edit_to_trace
from commscm.ccas.operators import (
    CRGuidedOperator,
    RandomOperator,
    RewardOnlyOperator,
    sink_fault_outcome,
)
from commscm.estimators.replay import DescendantReplayEngine, fault_marker_outcome
from commscm.runtime.mechanisms import MechanismRegistry


def _eval_method(name: str, op, traces, attr) -> dict:
    rows = []
    for tr in traces:
        y0 = sink_fault_outcome(tr.dag)
        report = attr.score(tr)
        prop = op.propose(tr, report)
        if not prop.edits:
            continue
        edit = prop.edits[0]
        new_tr = apply_edit_to_trace(tr, edit, outcome_fn=sink_fault_outcome)
        y1 = float(new_tr.outcome.reward)
        tgt = edit.target_event_id
        local_clean = False
        if tgt and tgt in new_tr.dag.events:
            local_clean = "FAULT_" not in new_tr.dag.events[tgt].message
        gold_edge = ("E0", "E1")
        hit_gold = (edit.source_event_id, edit.target_event_id) == gold_edge
        new_arch = op.apply(prop.base_architecture_id, prop)
        rows.append(
            {
                "run_id": tr.run_id,
                "edit": edit.model_dump(mode="json"),
                "y_before": y0,
                "y_after": y1,
                "improved": y1 > y0,
                "repaired": y1 >= 1.0 and y0 < 1.0,
                "local_clean": local_clean,
                "hit_gold_edge": hit_gold,
                "new_architecture_id": new_arch,
            }
        )
    n = len(rows)
    return {
        "method": name,
        "n": n,
        "success_before": sum(1 for r in rows if r["y_before"] >= 1.0) / n if n else 0.0,
        "success_after": sum(1 for r in rows if r["y_after"] >= 1.0) / n if n else 0.0,
        "mean_delta_y": sum(r["y_after"] - r["y_before"] for r in rows) / n if n else 0.0,
        "frac_repaired": sum(1 for r in rows if r["repaired"]) / n if n else 0.0,
        "frac_hit_gold_edge": sum(1 for r in rows if r["hit_gold_edge"]) / n if n else 0.0,
        "frac_local_clean": sum(1 for r in rows if r["local_clean"]) / n if n else 0.0,
        "edit_kind_counts": _count_kinds(rows),
        "examples": rows[:3],
    }


def _count_kinds(rows: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        k = r["edit"]["kind"]
        out[k] = out.get(k, 0) + 1
    return out


def main() -> None:
    traces = build_chain_fault_dataset(n_traces=40, n_events=12, seed=0)
    attr = DescendantReplayEstimator(
        DescendantReplayEngine(fault_marker_outcome, MechanismRegistry(), structural_cost_iters=0)
    )
    operators = {
        "random": RandomOperator(seed=0),
        "reward_only": RewardOnlyOperator(),
        "cr_guided": CRGuidedOperator(),
    }

    print("Phase B — single top-1 edit on chain-fault suite (sink_fault_outcome)")
    print(f"Traces: {len(traces)}")
    print(f"{'Method':<14} {'succ1':>7} {'repair':>7} {'hitGold':>8} {'dY':>7}")
    print("-" * 52)
    summary = {}
    for name, op_factory in operators.items():
        op = op_factory if name != "random" else RandomOperator(seed=0)
        if name == "reward_only":
            op = RewardOnlyOperator()
        if name == "cr_guided":
            op = CRGuidedOperator()
        op.registry = ArchitectureRegistry()
        row = _eval_method(name, op, traces, attr)
        summary[name] = row
        print(
            f"{name:<14} {row['success_after']:7.3f} {row['frac_repaired']:7.3f} "
            f"{row['frac_hit_gold_edge']:8.3f} {row['mean_delta_y']:7.3f}"
        )

    cr = summary["cr_guided"]
    rw = summary["reward_only"]
    rd = summary["random"]
    phase_b_pass = (
        cr["frac_hit_gold_edge"] > rw["frac_hit_gold_edge"]
        and cr["frac_hit_gold_edge"] > rd["frac_hit_gold_edge"]
        and cr["frac_repaired"] >= 0.9
    )
    verdict = {
        "phase_b_pass": phase_b_pass,
        "rule": (
            "CR-guided top-1 edit must hit the gold harmful edge more often than "
            "reward-only and random, and repair the terminal sink on >=90% of chain traces. "
            "(On a chain, cutting any edge can repair; gold-edge hit is the discriminating metric.)"
        ),
    }
    print("\nPhase B gate:", "PASS" if phase_b_pass else "FAIL")
    print(verdict)

    out = {
        "experiment": "week4_phase_b_single_edit",
        "phase": "B",
        "suite": "chain_fault",
        "iterative_ccas": False,
        "outcome": "sink_fault_outcome",
        "n": len(traces),
        "summary": {
            k: {kk: vv for kk, vv in v.items() if kk != "examples"}
            for k, v in summary.items()
        },
        "examples": {k: v["examples"] for k, v in summary.items()},
        "verdict": verdict,
    }
    path = Path("results/week4_phase_b.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
