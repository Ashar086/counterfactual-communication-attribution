"""WebArena adapter for Part VI.C (validation only; CommSCM core untouched)."""

from commscm.adapters.webarena.extract import (
    GOLD_EDGE,
    gold_event_for_poison,
    webarena_reward_outcome,
    webarena_state_to_run_trace,
)
from commscm.adapters.webarena.load import WebArenaInstance, load_vi_c_instance_list, load_webarena_instance
from commscm.adapters.webarena.mechanisms import make_webarena_sticky_registry
from commscm.adapters.webarena.official_env import assess_environment, capacity_report
from commscm.adapters.webarena.pipeline import prompt_hashes, run_webarena_pipeline
from commscm.adapters.webarena.state import WebArenaPipelineState

__all__ = [
    "GOLD_EDGE",
    "WebArenaInstance",
    "WebArenaPipelineState",
    "assess_environment",
    "capacity_report",
    "gold_event_for_poison",
    "load_vi_c_instance_list",
    "load_webarena_instance",
    "make_webarena_sticky_registry",
    "prompt_hashes",
    "run_webarena_pipeline",
    "webarena_reward_outcome",
    "webarena_state_to_run_trace",
]
