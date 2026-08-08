"""
Part V Stage 1 smoke: AutoGen adapter produces RunTrace; frozen CR scores it.

Does not modify Parts I–III. Live LLM unless USE_MOCK path unavailable —
requires OPENAI_API_KEY.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from credit_assignment.fault_injection import FaultInjector, PoisonMode
from credit_assignment.tasks import load_tasks
from credit_assignment import llm as _llm  # noqa: F401 — load .env
from commscm.adapters.autogen.extract import autogen_reward_outcome, autogen_state_to_run_trace
from commscm.adapters.autogen.mechanisms import make_autogen_sticky_registry
from commscm.adapters.autogen.pipeline import run_autogen_pipeline
from commscm.attribution.subset import SubsetAttributionEngine
from commscm.estimators.replay import DescendantReplayEngine


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY required for Stage 1 live smoke")
    os.environ["USE_MOCK_LLM"] = "0"
    task = load_tasks()[0]
    state = run_autogen_pipeline(
        task.prompt,
        fault_injector=FaultInjector(mode=PoisonMode.POISON_PLANNER),
        entry_point=task.entry_point,
        test_cases=list(task.test_cases),
        reference_solution=task.reference_solution,
    )
    tr = autogen_state_to_run_trace(state, run_id="stage1_smoke", task_id=task.task_id)
    report = SubsetAttributionEngine(
        DescendantReplayEngine(
            autogen_reward_outcome,
            make_autogen_sticky_registry(tr.dag),
            structural_cost_iters=0,
        ),
        {"C1", "C2", "C3", "C4", "C5"},
        name="AutoGenCR",
    ).score(tr)
    out = {
        "stage": 1,
        "framework": "autogen_agentchat",
        "task_id": task.task_id,
        "y": state.global_reward,
        "gold": tr.gold_fault_event_id,
        "cr_top1": report.predicted_top1,
        "cr_hit": report.predicted_top1 == tr.gold_fault_event_id,
        "n_events": len(tr.dag.events),
        "architecture_id": tr.architecture_id,
        "core_invariance": "adapter_only",
    }
    path = Path("results/part_v_stage1_smoke.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
