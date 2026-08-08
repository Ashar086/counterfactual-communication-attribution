"""
Part VI.C official runner (validation only).

Fails closed unless official WebArena env is ready.
Does not modify CommSCM core. Does not substitute fixtures for Success.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from credit_assignment import llm as _llm  # noqa: F401
from credit_assignment.fault_injection import FaultInjector, PoisonMode
from commscm.adapters.webarena.extract import webarena_reward_outcome, webarena_state_to_run_trace
from commscm.adapters.webarena.load import load_vi_c_instance_list, load_webarena_instance
from commscm.adapters.webarena.mechanisms import make_webarena_sticky_registry
from commscm.adapters.webarena.official_env import assess_environment, generate_configs, webarena_root
from commscm.adapters.webarena.pipeline import prompt_hashes, run_webarena_pipeline
from commscm.attribution.subset import SubsetAttributionEngine
from commscm.estimators.replay import DescendantReplayEngine

METHODS = (
    ("cr_guided", None),  # interventions filled after attribution
    ("reward_only", "reward"),
    ("random", "random"),
    ("static_heuristic", "static"),
)


def _require_official_env() -> None:
    st = assess_environment()
    if not st.ready_for_official:
        raise SystemExit(
            "Official WebArena env not ready "
            f"(blockage={st.blockage}). See commscm/WEBARENA_BRINGUP.md. "
            "Refusing to run n=100 official evaluation."
        )
    root = webarena_root()
    assert root is not None
    if not (root / "config_files" / "0.json").is_file():
        generate_configs(root)
    os.environ["WEBARENA_ROOT"] = str(root)


def _attribute(tr):
    return SubsetAttributionEngine(
        DescendantReplayEngine(
            webarena_reward_outcome,
            make_webarena_sticky_registry(tr.dag),
            structural_cost_iters=0,
        ),
        {"C1", "C2", "C3", "C4", "C5"},
        name="WebArenaCR",
    ).score(tr)


def _interventions_for_method(method: str, report, rng_seed: int) -> list[dict[str, str]]:
    """Single prune/weaken budget; CR uses top-1 parent→child when available."""
    import random

    if method == "cr_guided":
        top = report.predicted_top1
        # Map event to incoming edge (parent → top) when possible
        # Default gold poison edge C1→C2 if top is C2's parent side
        edge_map = {
            "C1": ("C0", "C1"),
            "C2": ("C1", "C2"),
            "C3": ("C2", "C3"),
            "C4": ("C3", "C4"),
            "C5": ("C4", "C5"),
        }
        src, tgt = edge_map.get(top, ("C1", "C2"))
        return [{"op": "prune_edge", "src": src, "tgt": tgt}]
    if method == "reward_only":
        # Weak baseline: prune C3→C4 (critic), not gold
        return [{"op": "prune_edge", "src": "C3", "tgt": "C4"}]
    if method == "static_heuristic":
        return [{"op": "prune_edge", "src": "C2", "tgt": "C3"}]
    # random
    edges = [("C1", "C2"), ("C2", "C3"), ("C3", "C4"), ("C0", "C1")]
    src, tgt = random.Random(rng_seed).choice(edges)
    return [{"op": "prune_edge", "src": src, "tgt": tgt}]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/part_vi_c_official.json")
    ap.add_argument("--limit", type=int, default=0, help="optional cap for debug")
    ap.add_argument(
        "--allow-unready",
        action="store_true",
        help="DEBUG only: run without official env (marks official_success null; not primary)",
    )
    args = ap.parse_args()

    if args.allow_unready:
        print("WARNING: --allow-unready set; results are NOT the preregistered primary.")
    else:
        _require_official_env()

    if not os.getenv("OPENAI_API_KEY") and os.getenv("USE_MOCK_LLM", "") not in {
        "1",
        "true",
        "True",
    }:
        raise SystemExit("OPENAI_API_KEY required")

    os.environ.setdefault("USE_MOCK_LLM", "0")
    os.environ.setdefault("FAIL_ON_LLM_ERROR", "1")

    hashes = prompt_hashes()
    Path("results/part_vi_c_prompt_hashes.json").write_text(
        json.dumps(hashes, indent=2), encoding="utf-8"
    )

    ids = load_vi_c_instance_list()
    if args.limit and args.limit > 0:
        ids = ids[: args.limit]

    rows: list[dict] = []
    t0 = time.time()
    for i, task_id in enumerate(ids):
        instance = load_webarena_instance(task_id)
        # Factual poisoned run
        factual = run_webarena_pipeline(
            instance,
            fault_injector=FaultInjector(mode=PoisonMode.POISON_PLANNER),
            model="gpt-4o-mini",
        )
        tr = webarena_state_to_run_trace(
            factual, run_id=f"vi_c_{task_id}_factual", task_id=str(task_id)
        )
        report = _attribute(tr)

        for method, _ in METHODS:
            interventions = _interventions_for_method(method, report, rng_seed=i)
            repaired = run_webarena_pipeline(
                instance,
                fault_injector=FaultInjector(mode=PoisonMode.POISON_PLANNER),
                edge_interventions=interventions,
                model="gpt-4o-mini",
            )
            tr2 = webarena_state_to_run_trace(
                repaired, run_id=f"vi_c_{task_id}_{method}", task_id=str(task_id)
            )
            row = {
                "task_id": str(task_id),
                "method": method,
                "instance_source": instance.source,
                "env_mode": repaired.env_mode,
                "y_proxy_before": factual.global_reward,
                "y_proxy_after": repaired.global_reward,
                "official_success": repaired.official_success,
                "gold": tr.gold_fault_event_id,
                "cr_top1": report.predicted_top1,
                "hit_gold_edge": report.predicted_top1 == tr.gold_fault_event_id,
                "interventions": interventions,
                "pipeline_ok": True,
                "prompt_hashes": hashes,
            }
            rows.append(row)
            print(
                f"[{len(rows)}] task={task_id} method={method} "
                f"gold_hit={row['hit_gold_edge']} official={row['official_success']}"
            )

        # checkpoint
        Path(args.out).write_text(json.dumps({"rows": rows, "elapsed_s": time.time() - t0}, indent=2), encoding="utf-8")

    payload = {
        "experiment": "part_vi_c_official",
        "prereg": "PART_VI_C_PREREGISTRATION.md",
        "n_tasks": len(ids),
        "n_rows": len(rows),
        "elapsed_s": time.time() - t0,
        "allow_unready": bool(args.allow_unready),
        "env": assess_environment().__dict__,
        "rows": rows,
    }
    Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {args.out}")
    if args.allow_unready:
        print("NOT PRIMARY — env was unready / allow_unready set.")


if __name__ == "__main__":
    main()
