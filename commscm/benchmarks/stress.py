"""Fault-cascade and noise-robustness suites (Week-2 closers)."""

from __future__ import annotations

import random
from copy import deepcopy

from pydantic import BaseModel, Field

from commscm.benchmarks.causal_comm_bench import (
    CHANNEL_OF,
    FAULT_TOOL,
    GoldFaultCase,
    binary_fault_outcome,
    build_pipeline,
    count_fault_markers,
)
from commscm.estimators.exact_replay import ExactReplayEngine
from commscm.experiments.week2_localize import (
    _coder_mechanism,
    _exec_mechanism,
    _review_mechanism,
)
from commscm.runtime.mechanisms import MechanismRegistry
from commscm.schema.events import CommunicationEvent, EventDAG, RunOutcome, RunTrace


def _memory_from_tool(event: CommunicationEvent, parent_msgs: dict[str, str]) -> str:
    """Cascade: corrupted tool ⇒ corrupted memory write."""
    tool = parent_msgs.get("C2", "")
    if tool.startswith("FAULT_") or "FAULT_" in tool:
        return 'FAULT_MEMORY_CASCADE: {"op":"write","key":"spec","value":"FROM_BAD_TOOL"}'
    return '{"op":"write","key":"spec","value":"return sum of a and b"}'


def build_cascade_mechanisms() -> MechanismRegistry:
    return MechanismRegistry(
        {
            "C3": _memory_from_tool,
            "C5": _coder_mechanism,
            "C6": _review_mechanism,
            "C7": _exec_mechanism,
        }
    )


def build_cascade_engine() -> ExactReplayEngine:
    """Outcome counts primary FAULT_ prefixes (root + cascaded writes)."""
    return ExactReplayEngine(
        outcome_fn=binary_fault_outcome,
        mechanisms=build_cascade_mechanisms(),
    )


def build_fault_cascade_dataset() -> list[GoldFaultCase]:
    """
    Root tool fault C2 propagates to memory C3 via mechanism, then to coder/review/exec.

    Gold root cause = C2 only (initiating communication event).
    """
    # Start from clean pipeline then set C2 fault; recompute C3..C7 with cascade mechs
    dag = build_pipeline({})
    # inject root fault
    c2 = dag.events["C2"]
    dag.events["C2"] = c2.model_copy(update={"message": FAULT_TOOL})

    mechs = build_cascade_mechanisms()
    messages = {eid: dag.events[eid].message for eid in dag.topological_order()}
    # C3 is child of... currently parents=[] for C3. Need C3←C2 for cascade!
    # Rebuild with C3 parents=[C2]
    return [_make_cascade_case()]


def _make_cascade_case() -> GoldFaultCase:
    parents = {
        "C0": [],
        "C1": [],
        "C2": [],
        "C3": ["C2"],  # memory depends on tool
        "C4": [],
        "C5": ["C1", "C2", "C3", "C4"],
        "C6": ["C5"],
        "C7": ["C6"],
    }
    senders = {
        "C0": "user",
        "C1": "planner",
        "C2": "tool",
        "C3": "memory",
        "C4": "retriever",
        "C5": "coder",
        "C6": "reviewer",
        "C7": "executor",
    }
    receivers = {
        "C0": "planner",
        "C1": "coder",
        "C2": "coder",
        "C3": "coder",
        "C4": "coder",
        "C5": "reviewer",
        "C6": "executor",
        "C7": "user",
    }
    msgs = {
        "C0": "Task: implement add(a,b) returning a+b.",
        "C1": "Plan: implement def add(a,b): return a+b",
        "C2": FAULT_TOOL,
        "C3": "PLACEHOLDER",
        "C4": '{"docs":["PEP guidance: pure function add"]}',
        "C5": "PLACEHOLDER",
        "C6": "PLACEHOLDER",
        "C7": "PLACEHOLDER",
    }
    mechs = build_cascade_mechanisms()
    # materialize mechanized nodes in order
    for eid in ["C3", "C5", "C6", "C7"]:
        ev = CommunicationEvent(
            event_id=eid,
            sender=senders[eid],
            receiver=receivers[eid],
            channel=CHANNEL_OF[eid],
            message=msgs[eid],
            time_index=["C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7"].index(eid),
            parents=list(parents[eid]),
        )
        parent_msgs = {p: msgs[p] for p in parents[eid]}
        msgs[eid] = mechs.get(eid)(ev, parent_msgs)

    dag = EventDAG()
    for i, eid in enumerate(["C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7"]):
        dag.add(
            CommunicationEvent(
                event_id=eid,
                sender=senders[eid],
                receiver=receivers[eid],
                channel=CHANNEL_OF[eid],
                message=msgs[eid],
                time_index=i,
                parents=list(parents[eid]),
            )
        )

    y = binary_fault_outcome(dag)
    assert y == 0.0
    assert dag.events["C3"].message.startswith("FAULT_MEMORY_CASCADE")
    trace = RunTrace(
        run_id="CASC1_tool_to_memory",
        task_id="synth_fault_cascade",
        architecture_id="causal_comm_bench_cascade_v0",
        dag=dag,
        outcome=RunOutcome(
            reward=y,
            success=False,
            metrics={"fault_type": "cascade_tool_to_memory", "root": "C2"},
        ),
        gold_fault_event_id="C2",
        gold_fault_event_ids=["C2"],  # root cause only
        poison_mode="cascade_tool_to_memory",
        extra={"cascade_symptoms": ["C3", "C5", "C6", "C7"]},
    )
    return GoldFaultCase(
        case_id="CASC1_tool_to_memory",
        fault_type="cascade_tool_to_memory",
        true_event_id="C2",
        true_event_ids=["C2"],
        trace=trace,
    )


def inject_semantic_noise(
    dag: EventDAG,
    *,
    rate: float,
    seed: int,
    protect_ids: set[str],
) -> EventDAG:
    """
    Append semantic noise tokens to non-protected events with probability `rate`.

    Never introduces FAULT_ markers. Deterministic given seed.
    """
    if not 0.0 <= rate <= 1.0:
        raise ValueError("rate must be in [0, 1]")
    rng = random.Random(seed)
    out = EventDAG()
    for eid in dag.topological_order():
        e = dag.events[eid]
        msg = e.message
        if eid not in protect_ids and rng.random() < rate:
            msg = f"{msg} [NOISE_{rng.randint(1000, 9999)} semantic drift]"
        out.add(e.model_copy(update={"message": msg}, deep=True))
    return out


def noise_perturbed_case(
    case: GoldFaultCase,
    *,
    rate: float,
    seed: int,
) -> GoldFaultCase:
    protect = set(case.true_event_ids)
    noisy_dag = inject_semantic_noise(
        case.trace.dag, rate=rate, seed=seed, protect_ids=protect
    )
    y = binary_fault_outcome(noisy_dag)
    tr = case.trace.model_copy(
        update={
            "run_id": f"{case.case_id}_noise{int(rate*100)}_s{seed}",
            "dag": noisy_dag,
            "outcome": RunOutcome(reward=y, success=y >= 1.0, metrics={"noise_rate": rate}),
            "extra": {**case.trace.extra, "noise_rate": rate, "noise_seed": seed},
        },
        deep=True,
    )
    return GoldFaultCase(
        case_id=tr.run_id,
        fault_type=f"{case.fault_type}_noise",
        true_event_id=case.true_event_id,
        true_event_ids=list(case.true_event_ids),
        trace=tr,
    )
