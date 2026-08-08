"""
SWE-bench Verified adapter (Part VI) — benchmark-specific only.

Scope: SWE-bench Verified *problem statements* → multi-agent → RunTrace.
Not the official Docker resolve@1 harness (logged as external-validity limit).

Core Invariance: no IF-C-SCM / CR / replay / CCAS changes.
"""

from commscm.adapters.swebench.extract import (
    swebench_reward_outcome,
    swebench_state_to_run_trace,
)
from commscm.adapters.swebench.load import SWEBenchInstance, load_swebench_verified_subset
from commscm.adapters.swebench.pipeline import run_swebench_pipeline
from commscm.adapters.swebench.state import SWEBenchPipelineState

__all__ = [
    "SWEBenchInstance",
    "SWEBenchPipelineState",
    "load_swebench_verified_subset",
    "run_swebench_pipeline",
    "swebench_state_to_run_trace",
    "swebench_reward_outcome",
]
