"""Credit Assignment in Compound Agentic Systems — experimental toolkit."""

from credit_assignment.fault_injection import FaultInjector, PoisonMode
from credit_assignment.graph import build_pipeline_graph, run_pipeline
from credit_assignment.meta_agent import approximate_credit_assignment, evaluate_meta_agent
from credit_assignment.shadow_buffer import ShadowBuffer
from credit_assignment.shapley import blame_ranking, calculate_exact_shapley
from credit_assignment.state import AgentState
from credit_assignment.tasks import SoftwareTask, load_tasks

__all__ = [
    "AgentState",
    "FaultInjector",
    "PoisonMode",
    "ShadowBuffer",
    "SoftwareTask",
    "approximate_credit_assignment",
    "blame_ranking",
    "build_pipeline_graph",
    "calculate_exact_shapley",
    "evaluate_meta_agent",
    "load_tasks",
    "run_pipeline",
]
