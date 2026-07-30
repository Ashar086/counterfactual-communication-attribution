"""Phase B chain suite: single harmful edge on a unique path to the sink."""

from __future__ import annotations

from commscm.benchmarks.causal_comm_bench import FAULT_TEXT
from commscm.ccas.apply_edit import rematerialize
from commscm.schema.events import Channel, CommunicationEvent, EventDAG, RunOutcome, RunTrace


def build_chain_fault_trace(*, n_events: int = 12, seed: int = 0) -> RunTrace:
    """
    Linear chain E0→E1→...→E{n-1} with FAULT on E0.

    A single prune/weaken/verifier on edge E0→E1 can stop propagation to the sink.
    """
    if n_events < 4:
        raise ValueError("n_events must be >= 4")
    dag = EventDAG()
    dag.add(
        CommunicationEvent(
            event_id="E0",
            sender="src",
            receiver="n1",
            channel=Channel.TEXT,
            message=FAULT_TEXT,
            time_index=0,
        )
    )
    for i in range(1, n_events):
        dag.add(
            CommunicationEvent(
                event_id=f"E{i}",
                sender=f"n{i}",
                receiver=f"n{i+1}",
                channel=Channel.TEXT,
                message=f"placeholder_E{i}",
                time_index=i,
                parents=[f"E{i-1}"],
            )
        )
    dag = rematerialize(dag)
    return RunTrace(
        run_id=f"chain_fault_{n_events}_s{seed}",
        task_id="week4_phase_b_chain",
        architecture_id=f"chain_v0_{n_events}",
        dag=dag,
        outcome=RunOutcome(reward=0.0, success=False),
        gold_fault_event_id="E0",
        gold_fault_event_ids=["E0"],
        poison_mode="chain_fault",
        extra={"gold_harmful_edges": [("E0", "E1")]},
    )


def build_chain_fault_dataset(*, n_traces: int = 40, n_events: int = 12, seed: int = 0) -> list[RunTrace]:
    return [build_chain_fault_trace(n_events=n_events, seed=seed + i) for i in range(n_traces)]
