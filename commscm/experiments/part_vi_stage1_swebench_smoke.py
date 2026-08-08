"""
Part VI Stage 1 smoke: SWE-bench Verified–shaped → RunTrace; frozen CR scores it.

Adapter-only. Does not modify Parts I–III.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from credit_assignment import llm as _llm  # noqa: F401 — load .env
from credit_assignment.fault_injection import FaultInjector, PoisonMode
from commscm.adapters.swebench.extract import swebench_reward_outcome, swebench_state_to_run_trace
from commscm.adapters.swebench.load import load_swebench_verified_subset, offline_fixture_instances
from commscm.adapters.swebench.mechanisms import make_swebench_sticky_registry
from commscm.adapters.swebench.pipeline import run_swebench_pipeline
from commscm.attribution.subset import SubsetAttributionEngine
from commscm.estimators.replay import DescendantReplayEngine


def _load_one():
    try:
        insts = load_swebench_verified_subset(n=1, seed=42)
        return insts[0], "huggingface:princeton-nlp/SWE-bench_Verified"
    except Exception as exc:  # noqa: BLE001
        print(f"HF load failed ({type(exc).__name__}: {exc}); using offline fixture")
        return offline_fixture_instances(1)[0], "offline_fixture"


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY required for Stage 1 live smoke")
    os.environ["USE_MOCK_LLM"] = "0"
    os.environ["FAIL_ON_LLM_ERROR"] = "1"

    instance, source = _load_one()
    state = run_swebench_pipeline(
        instance,
        fault_injector=FaultInjector(mode=PoisonMode.POISON_PLANNER),
    )
    tr = swebench_state_to_run_trace(
        state, run_id="part_vi_stage1_smoke", task_id=instance.instance_id
    )
    report = SubsetAttributionEngine(
        DescendantReplayEngine(
            swebench_reward_outcome,
            make_swebench_sticky_registry(tr.dag),
            structural_cost_iters=0,
        ),
        {"C1", "C2", "C3", "C4", "C5"},
        name="SWEBenchCR",
    ).score(tr)
    out = {
        "stage": 1,
        "benchmark": "SWE-bench_Verified_shaped",
        "instance_source": source,
        "instance_id": instance.instance_id,
        "y": state.global_reward,
        "gold": tr.gold_fault_event_id,
        "cr_top1": report.predicted_top1,
        "cr_hit": report.predicted_top1 == tr.gold_fault_event_id,
        "n_events": len(tr.dag.events),
        "architecture_id": tr.architecture_id,
        "core_invariance": "adapter_only",
        "scope_note": (
            "Problem statements from SWE-bench Verified (or fixtures); "
            "not official Docker resolve@1"
        ),
    }
    path = Path("results/part_vi_stage1_swebench_smoke.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    print(f"Wrote {path}")
    if not out["cr_hit"]:
        raise SystemExit("Stage 1 smoke: CR missed gold (investigate adapter before Stage 2)")


if __name__ == "__main__":
    main()
