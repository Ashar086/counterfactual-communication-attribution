"""
Part VI.C smoke: WebArena adapter → RunTrace; frozen CR scores it.

Adapter-only. Does not modify CommSCM core.
Uses offline fixtures unless WEBARENA_ROOT points at generated configs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from credit_assignment import llm as _llm  # noqa: F401 — load .env
from credit_assignment.fault_injection import FaultInjector, PoisonMode
from commscm.adapters.webarena.extract import webarena_reward_outcome, webarena_state_to_run_trace
from commscm.adapters.webarena.load import load_vi_c_instance_list, load_webarena_instance
from commscm.adapters.webarena.mechanisms import make_webarena_sticky_registry
from commscm.adapters.webarena.pipeline import prompt_hashes, run_webarena_pipeline
from commscm.attribution.subset import SubsetAttributionEngine
from commscm.estimators.replay import DescendantReplayEngine


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY required for VI.C live smoke (or set USE_MOCK_LLM=1)")
    if os.getenv("USE_MOCK_LLM", "").strip() not in {"1", "true", "True"}:
        os.environ["USE_MOCK_LLM"] = "0"
        os.environ["FAIL_ON_LLM_ERROR"] = "1"

    ids = load_vi_c_instance_list()
    task_id = ids[0]  # 743 — first locked ID
    instance = load_webarena_instance(task_id)

    hashes = prompt_hashes()
    hash_path = Path("results/part_vi_c_prompt_hashes.json")
    hash_path.parent.mkdir(parents=True, exist_ok=True)
    hash_path.write_text(json.dumps(hashes, indent=2), encoding="utf-8")

    state = run_webarena_pipeline(
        instance,
        fault_injector=FaultInjector(mode=PoisonMode.POISON_PLANNER),
        model=os.getenv("COMMSCM_MODEL", "gpt-4o-mini"),
    )
    tr = webarena_state_to_run_trace(
        state, run_id="part_vi_c_smoke", task_id=instance.task_id
    )
    report = SubsetAttributionEngine(
        DescendantReplayEngine(
            webarena_reward_outcome,
            make_webarena_sticky_registry(tr.dag),
            structural_cost_iters=0,
        ),
        {"C1", "C2", "C3", "C4", "C5"},
        name="WebArenaCR",
    ).score(tr)

    out = {
        "stage": "vi_c_smoke",
        "benchmark": "WebArena",
        "prereg": "PART_VI_C_PREREGISTRATION.md",
        "core_invariance": "adapter_only",
        "instance_source": instance.source,
        "task_id": instance.task_id,
        "y_proxy": state.global_reward,
        "official_success": state.official_success,
        "gold": tr.gold_fault_event_id,
        "gold_edge": tr.extra.get("gold_edge"),
        "cr_top1": report.predicted_top1,
        "cr_hit": report.predicted_top1 == tr.gold_fault_event_id,
        "n_events": len(tr.dag.events),
        "architecture_id": tr.architecture_id,
        "prompt_hashes": hashes,
        "env_mode": state.env_mode,
        "scope_note": (
            "Smoke validates RunTrace extraction + CR localization under poison; "
            "not the full n=100 official Success evaluation"
        ),
    }
    path = Path("results/part_vi_c_smoke.json")
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    print(f"Wrote {path}")
    print(f"Wrote {hash_path}")
    if not out["cr_hit"]:
        raise SystemExit("VI.C smoke: CR missed gold (investigate adapter before full run)")


if __name__ == "__main__":
    main()
