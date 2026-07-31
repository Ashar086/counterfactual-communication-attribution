"""
Week 6 — live single-edit repair (frozen RQ).

Live trace → CR → one prune/weaken → re-run → Δ outcome.
No verifiers. No search. No multi-edit. Failure taxonomy F1–F6.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from collections import Counter, defaultdict
from pathlib import Path

from credit_assignment.fault_injection import FaultInjector, PoisonMode
from credit_assignment.graph import run_pipeline
from credit_assignment.tasks import load_tasks
from commscm.attribution.subset import SubsetAttributionEngine
from commscm.ccas.interfaces import ArchitectureEdit
from commscm.ccas.operators import (
    CRGuidedOperator,
    RandomOperator,
    RewardOnlyOperator,
    gold_harmful_edges,
)
from commscm.estimators.replay import DescendantReplayEngine
from commscm.traces.langgraph_extract import agent_state_to_run_trace, langgraph_reward_outcome
from commscm.traces.langgraph_live_edit import (
    edit_to_intervention,
    first_prune_or_weaken,
    intervention_supported,
)
from commscm.traces.langgraph_mechanisms import make_langgraph_sticky_registry

AGENT_EVENTS = {"C1", "C2", "C3", "C4", "C5"}
MODES = (PoisonMode.POISON_PLANNER, PoisonMode.POISON_CODER, PoisonMode.POISON_REVIEWER)
METHODS = ("cr_guided", "reward_only", "random")


def score_trace(tr):
    mechs = make_langgraph_sticky_registry(tr.dag)
    return SubsetAttributionEngine(
        DescendantReplayEngine(langgraph_reward_outcome, mechs, structural_cost_iters=0),
        AGENT_EVENTS,
        name="LangGraphCR",
    ).score(tr)


def sink_structurally_valid(state) -> bool:
    """Executor received a non-empty code artifact (sink attached)."""
    code = (state.code or "").strip()
    return bool(code)


def classify_failure(
    *,
    attribution_ok: bool,
    extract_ok: bool,
    pipeline_ok: bool,
    repair_ok: bool,
    attribution_correct: bool,
    hit_gold_edge: bool,
    y_before: float,
    y_after: float | None,
    sink_valid: bool,
    edit_supported: bool,
    n_edits: int,
) -> str | None:
    """
    Exactly one failure code when the task is not fully repaired; None if Y_after≥1.

    F3 covers local improvement without full repair (still reported, not hidden).
    """
    repaired = y_before < 1.0 and y_after is not None and y_after >= 1.0
    improved = y_after is not None and y_after > y_before

    if repaired and repair_ok and n_edits == 1 and sink_valid:
        return None

    if not pipeline_ok or not extract_ok or not attribution_ok or not repair_ok:
        return "F5"
    if not edit_supported or not sink_valid or n_edits != 1:
        return "F6"
    if improved and not repaired:
        return "F3"
    if not attribution_correct:
        return "F1"
    if attribution_correct and hit_gold_edge and not improved:
        return "F4"  # gold pathway edit; reward did not move
    if attribution_correct and not hit_gold_edge:
        return "F2"
    return "F2"


def _latency_ms(state) -> float:
    total = 0.0
    for k, v in (state.trace_log or {}).items():
        if k.startswith("_") or not isinstance(v, dict):
            continue
        total += float(v.get("latency_ms") or 0.0)
    return total


def run_method_on_failure(
    *,
    task,
    mode: PoisonMode,
    method: str,
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
        "method": method,
        "temperature": temperature,
        "seed": seed,
        "n_edits": 0,
        "pipeline_ok": False,
        "extract_ok": False,
        "attribution_ok": False,
        "repair_pipeline_ok": False,
        "failures": [],
    }
    t0 = time.perf_counter()
    injector = FaultInjector(mode=mode)

    try:
        state0 = run_pipeline(
            task.prompt,
            fault_injector=injector,
            entry_point=task.entry_point,
            test_cases=list(task.test_cases),
            reference_solution=task.reference_solution,
        )
        row["pipeline_ok"] = True
        row["y_before"] = float(state0.global_reward)
        row["latency_before_ms"] = _latency_ms(state0)
        row["sink_valid_before"] = sink_structurally_valid(state0)
    except Exception as exc:  # noqa: BLE001
        row["failures"].append({"stage": "pipeline", "error": f"{type(exc).__name__}: {exc}"})
        row["failure_code"] = "F5"
        row["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return row

    # Only repair failures (pre-registered: intervene on unsuccessful tasks)
    if row["y_before"] >= 1.0:
        row["skipped"] = True
        row["skip_reason"] = "already_success"
        row["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return row

    try:
        tr = agent_state_to_run_trace(
            state0, run_id=f"w6_{run_idx}_{method}_{mode.value}_{task.task_id}"
        )
        row["extract_ok"] = True
        row["gold"] = tr.gold_fault_event_id
        row["gold_edges"] = sorted(gold_harmful_edges(tr))
    except Exception as exc:  # noqa: BLE001
        row["failures"].append({"stage": "extract", "error": f"{type(exc).__name__}: {exc}"})
        row["failure_code"] = "F5"
        row["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return row

    try:
        report = score_trace(tr)
        row["attribution_ok"] = True
        row["cr_top1"] = report.predicted_top1
        row["attribution_correct"] = report.predicted_top1 == tr.gold_fault_event_id
        row["factual_reward"] = report.factual_reward
    except Exception as exc:  # noqa: BLE001
        row["failures"].append(
            {"stage": "attribution", "error": f"{type(exc).__name__}: {exc}"}
        )
        row["failure_code"] = "F5"
        row["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return row

    if method == "cr_guided":
        op = CRGuidedOperator()
    elif method == "reward_only":
        op = RewardOnlyOperator()
    else:
        op = RandomOperator(seed=run_idx)

    prop = op.propose(tr, report)
    time_index = {eid: ev.time_index for eid, ev in tr.dag.events.items()}
    # Action-space top1 only for CR-guided. Controls use their own proposal order
    # (do not leak CR's predicted_top1 into reward-only / random).
    top1_for_action = report.predicted_top1 if method == "cr_guided" else None
    if method != "cr_guided" and prop.motivating_event_ids:
        top1_for_action = prop.motivating_event_ids[0]
    edit = first_prune_or_weaken(
        prop.edits,
        top1_event=top1_for_action,
        target_time_index=time_index if method == "cr_guided" else None,
    )
    if edit is None:
        row["failure_code"] = "F6"
        row["failures"].append({"stage": "edit", "error": "no_prune_or_weaken"})
        row["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return row

    row["n_edits"] = 1
    row["edit"] = edit.model_dump(mode="json")
    row["edit_key"] = f"{edit.kind.value}:{edit.source_event_id}->{edit.target_event_id}"
    gold_e = gold_harmful_edges(tr)
    row["hit_gold_edge"] = (edit.source_event_id, edit.target_event_id) in gold_e
    supported = intervention_supported(edit)
    row["edit_supported"] = supported
    if not supported:
        row["failure_code"] = "F6"
        row["failures"].append({"stage": "edit", "error": "unsupported_live_edge"})
        row["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return row

    iv = edit_to_intervention(edit)
    assert iv is not None

    try:
        state1 = run_pipeline(
            task.prompt,
            fault_injector=FaultInjector(mode=mode),
            entry_point=task.entry_point,
            test_cases=list(task.test_cases),
            reference_solution=task.reference_solution,
            edge_interventions=[iv],
        )
        row["repair_pipeline_ok"] = True
        row["y_after"] = float(state1.global_reward)
        row["latency_after_ms"] = _latency_ms(state1)
        row["sink_valid_after"] = sink_structurally_valid(state1)
        row["delta_y"] = row["y_after"] - row["y_before"]
        row["latency_delta_ms"] = row["latency_after_ms"] - row["latency_before_ms"]
    except Exception as exc:  # noqa: BLE001
        row["failures"].append({"stage": "repair", "error": f"{type(exc).__name__}: {exc}"})
        row["traceback"] = traceback.format_exc()[-1500:]
        row["failure_code"] = "F5"
        row["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return row

    improved = row["y_after"] > row["y_before"]
    repaired = row["y_before"] < 1.0 and row["y_after"] >= 1.0
    row["improved"] = improved
    row["repaired"] = repaired
    row["success"] = (
        repaired or improved
    ) and row["sink_valid_after"] and row["n_edits"] == 1
    row["failure_code"] = classify_failure(
        attribution_ok=True,
        extract_ok=True,
        pipeline_ok=True,
        repair_ok=row["repair_pipeline_ok"],
        attribution_correct=bool(row.get("attribution_correct")),
        hit_gold_edge=bool(row.get("hit_gold_edge")),
        y_before=row["y_before"],
        y_after=row.get("y_after"),
        sink_valid=bool(row.get("sink_valid_after")),
        edit_supported=True,
        n_edits=1,
    )
    row["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return row


def aggregate(rows: list[dict]) -> dict:
    attempted = [r for r in rows if not r.get("skipped")]
    by_method: dict[str, dict] = {}
    for method in METHODS:
        mrows = [r for r in attempted if r.get("method") == method]
        n = len(mrows)
        repaired = [r for r in mrows if r.get("repaired")]
        success = [r for r in mrows if r.get("success")]
        scored = [r for r in mrows if r.get("y_after") is not None]
        fail_counts = Counter(r.get("failure_code") for r in mrows if r.get("failure_code"))
        # Repair Attribution Precision: among successful repairs, fraction via gold edge
        n_rep = len(repaired)
        repair_attr_prec = (
            sum(1 for r in repaired if r.get("hit_gold_edge")) / n_rep if n_rep else None
        )
        by_method[method] = {
            "n": n,
            "n_with_after": len(scored),
            "task_success_before": (
                sum(1 for r in mrows if r.get("y_before", 0) >= 1.0) / n if n else 0.0
            ),
            "task_success_after": (
                sum(1 for r in scored if r.get("y_after", 0) >= 1.0) / len(scored)
                if scored
                else 0.0
            ),
            "delta_task_success": None,
            "frac_repaired": len(repaired) / n if n else 0.0,
            "frac_success": len(success) / n if n else 0.0,
            "mean_delta_y": (
                sum(r.get("delta_y", 0.0) for r in scored) / len(scored) if scored else 0.0
            ),
            "gold_edge_hit_rate": (
                sum(1 for r in mrows if r.get("hit_gold_edge")) / n if n else 0.0
            ),
            "edit_precision": (
                sum(1 for r in mrows if r.get("hit_gold_edge")) / n if n else 0.0
            ),
            "repair_attribution_precision": repair_attr_prec,
            "mean_latency_delta_ms": (
                sum(r.get("latency_delta_ms", 0.0) for r in scored) / len(scored)
                if scored
                else None
            ),
            "failure_taxonomy": dict(fail_counts),
            "pipeline_ok_rate": (
                sum(1 for r in mrows if r.get("pipeline_ok")) / n if n else 0.0
            ),
        }
        b = by_method[method]
        b["delta_task_success"] = b["task_success_after"] - b["task_success_before"]

    # Edit stability: CR edit_key agreement per (task, poison_mode)
    # (cross-mode agreement on the same task is expected to be low)
    cr_by_group: dict[tuple[str, str], list[str]] = defaultdict(list)
    for r in attempted:
        if r.get("method") == "cr_guided" and r.get("edit_key"):
            cr_by_group[(r["task_id"], r["poison_mode"])].append(r["edit_key"])
    edit_stability = []
    for (tid, mode), keys in sorted(cr_by_group.items()):
        if len(keys) < 2:
            # still record singleton for completeness
            edit_stability.append(
                {
                    "task_id": tid,
                    "poison_mode": mode,
                    "n": len(keys),
                    "modal_edit": keys[0] if keys else None,
                    "agreement": 1.0 if keys else None,
                }
            )
            continue
        modal, _ = Counter(keys).most_common(1)[0]
        agree = sum(1 for k in keys if k == modal) / len(keys)
        edit_stability.append(
            {
                "task_id": tid,
                "poison_mode": mode,
                "n": len(keys),
                "modal_edit": modal,
                "agreement": agree,
            }
        )
    multi = [x for x in edit_stability if (x.get("n") or 0) >= 2 and x.get("agreement") is not None]
    # Also: modal edit agreement within each poison mode (across tasks)
    by_mode_keys: dict[str, list[str]] = defaultdict(list)
    for r in attempted:
        if r.get("method") == "cr_guided" and r.get("edit_key"):
            by_mode_keys[r["poison_mode"]].append(r["edit_key"])
    edit_stability_by_mode = {}
    for mode, keys in sorted(by_mode_keys.items()):
        modal, _ = Counter(keys).most_common(1)[0]
        edit_stability_by_mode[mode] = {
            "n": len(keys),
            "modal_edit": modal,
            "agreement": sum(1 for k in keys if k == modal) / len(keys) if keys else None,
        }
    mode_agreements = [
        v["agreement"]
        for v in edit_stability_by_mode.values()
        if v.get("agreement") is not None
    ]
    mean_edit_stab = (
        sum(x["agreement"] for x in multi) / len(multi)
        if multi
        else (sum(mode_agreements) / len(mode_agreements) if mode_agreements else None)
    )


    cr = by_method["cr_guided"]
    ro = by_method["reward_only"]
    rnd = by_method["random"]
    gate = (
        cr["n"] > 0
        and cr["pipeline_ok_rate"] >= 0.9
        and cr["frac_repaired"] > ro["frac_repaired"]
        and cr["frac_repaired"] > rnd["frac_repaired"]
    )
    return {
        "n_attempted_rows": len(attempted),
        "n_skipped_success": sum(1 for r in rows if r.get("skipped")),
        "by_method": by_method,
        "edit_stability_by_task": edit_stability,
        "edit_stability_by_mode": edit_stability_by_mode,
        "mean_edit_stability": mean_edit_stab,
        "week6_gate_pass": gate,
    }


def build_schedule(n_runs: int, tasks: list) -> list[tuple]:
    """
    Balanced schedule: methods and poison modes are *independent*.

    Within each block of 3: same (task, mode), all three methods.
    Modes cycle slower than methods so CR/reward/random each see every poison.
    """
    schedule = []
    i = 0
    while len(schedule) < n_runs:
        method = METHODS[i % len(METHODS)]
        mode = MODES[(i // len(METHODS)) % len(MODES)]
        task = tasks[(i // (len(METHODS) * len(MODES))) % len(tasks)]
        schedule.append((task, mode, method, len(schedule)))
        i += 1
    return schedule


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-runs", type=int, default=60)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", type=str, default="results/week6_live_repair.json")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        import credit_assignment.llm  # noqa: F401
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY required for live Week 6 runs")

    os.environ["USE_MOCK_LLM"] = "0"
    os.environ["FAIL_ON_LLM_ERROR"] = "1"

    tasks = load_tasks()
    schedule = build_schedule(args.n_runs, tasks)
    rows: list[dict] = []
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Week 6 live repair: n_runs={args.n_runs} temp={args.temperature}")
    print("RQ: Can communication attribution improve a real multi-agent system via one edit?")

    for task, mode, method, idx in schedule:
        print(
            f"[{idx+1}/{args.n_runs}] {method} {mode.value} task={task.task_id} ...",
            flush=True,
        )
        row = run_method_on_failure(
            task=task,
            mode=mode,
            method=method,
            run_idx=idx,
            temperature=args.temperature,
            seed=args.seed,
        )
        rows.append(row)
        if row.get("skipped"):
            print("  skip (already success)", flush=True)
        else:
            print(
                f"  y={row.get('y_before')}->{row.get('y_after')} "
                f"repaired={row.get('repaired')} fail={row.get('failure_code')} "
                f"edit={row.get('edit_key')}",
                flush=True,
            )
        if (idx + 1) % 5 == 0 or idx + 1 == args.n_runs:
            summary = aggregate(rows)
            out_path.write_text(
                json.dumps(
                    {
                        "experiment": "week6_live_repair",
                        "partial": idx + 1 < args.n_runs,
                        "summary": summary,
                        "rows": rows,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            cr = summary["by_method"]["cr_guided"]
            print(
                f"  checkpoint CR repaired={cr['frac_repaired']:.3f} "
                f"n={cr['n']} gate={summary['week6_gate_pass']}",
                flush=True,
            )

    summary = aggregate(rows)
    payload = {
        "experiment": "week6_live_repair",
        "research_question": (
            "Can communication attribution improve a real multi-agent system "
            "through a single architecture edit?"
        ),
        "claim_note": (
            "Live LangGraph re-run after one prune/weaken. "
            "Not SWE-bench/WebArena. No verifiers. Failure taxonomy F1–F6 reported."
        ),
        "summary": summary,
        "rows": rows,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("\n=== Week 6 summary ===")
    print(json.dumps(summary, indent=2))
    print(f"gate={'PASS' if summary['week6_gate_pass'] else 'FAIL'}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
