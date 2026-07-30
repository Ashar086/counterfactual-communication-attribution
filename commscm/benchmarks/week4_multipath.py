"""Multi-path fault suite: both branches must be neutralized (Phase D / H2-lite)."""

from __future__ import annotations

from commscm.benchmarks.causal_comm_bench import FAULT_TEXT
from commscm.ccas.apply_edit import rematerialize
from commscm.schema.events import Channel, CommunicationEvent, EventDAG, RunOutcome, RunTrace


def build_multipath_fault_trace(*, branch_len: int = 3, seed: int = 0) -> RunTrace:
    """
    E0(FAULT) fans into two chains that merge before the sink:

        E0 ──► A1 ► … ► Ak ──┐
                              ├──► M ► S
        E0 ──► B1 ► … ► Bk ──┘

    One edit cannot repair: both paths must be cut or cleaned.
    Gold harmful edges: (E0,A1) and (E0,B1).
    """
    if branch_len < 1:
        raise ValueError("branch_len must be >= 1")
    dag = EventDAG()
    t = 0
    dag.add(
        CommunicationEvent(
            event_id="E0",
            sender="src",
            receiver="split",
            channel=Channel.TEXT,
            message=FAULT_TEXT,
            time_index=t,
        )
    )
    t += 1
    a_ids = []
    b_ids = []
    prev_a, prev_b = "E0", "E0"
    for i in range(1, branch_len + 1):
        aid, bid = f"A{i}", f"B{i}"
        dag.add(
            CommunicationEvent(
                event_id=aid,
                sender=f"a{i}",
                receiver=f"a{i+1}",
                channel=Channel.TEXT,
                message=f"placeholder_{aid}",
                time_index=t,
                parents=[prev_a],
            )
        )
        t += 1
        dag.add(
            CommunicationEvent(
                event_id=bid,
                sender=f"b{i}",
                receiver=f"b{i+1}",
                channel=Channel.TEXT,
                message=f"placeholder_{bid}",
                time_index=t,
                parents=[prev_b],
            )
        )
        t += 1
        a_ids.append(aid)
        b_ids.append(bid)
        prev_a, prev_b = aid, bid

    dag.add(
        CommunicationEvent(
            event_id="M",
            sender="merge",
            receiver="sink",
            channel=Channel.TEXT,
            message="placeholder_M",
            time_index=t,
            parents=[prev_a, prev_b],
        )
    )
    t += 1
    dag.add(
        CommunicationEvent(
            event_id="S",
            sender="sink",
            receiver="user",
            channel=Channel.TEXT,
            message="placeholder_S",
            time_index=t,
            parents=["M"],
        )
    )
    dag = rematerialize(dag)
    gold = [("E0", "A1"), ("E0", "B1")]
    return RunTrace(
        run_id=f"multipath_b{branch_len}_s{seed}",
        task_id="week4_phase_d_multipath",
        architecture_id=f"multipath_v0_b{branch_len}",
        dag=dag,
        outcome=RunOutcome(reward=0.0, success=False),
        gold_fault_event_id="E0",
        gold_fault_event_ids=["E0"],
        poison_mode="multipath_fault",
        extra={"gold_harmful_edges": gold, "min_edits_to_repair": 2},
    )


def build_multipath_fault_dataset(
    *, n_traces: int = 30, branch_len: int = 3, seed: int = 0
) -> list[RunTrace]:
    return [
        build_multipath_fault_trace(branch_len=branch_len, seed=seed + i)
        for i in range(n_traces)
    ]
