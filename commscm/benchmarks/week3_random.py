"""Synthetic random deterministic traces for Week-3 approximation study."""

from __future__ import annotations

import random

from commscm.benchmarks.causal_comm_bench import CHANNEL_OF, FAULT_MEMORY, FAULT_RETRIEVAL, FAULT_TEXT, FAULT_TOOL
from commscm.schema.events import Channel, CommunicationEvent, EventDAG, RunOutcome, RunTrace

FAULT_BY_CHANNEL = {
    Channel.TEXT: FAULT_TEXT,
    Channel.TOOL: FAULT_TOOL,
    Channel.MEMORY: FAULT_MEMORY,
    Channel.RETRIEVAL: FAULT_RETRIEVAL,
}


def build_random_trace(seed: int, *, n_events: int = 16) -> RunTrace:
    rng = random.Random(seed)
    if n_events < 8:
        raise ValueError("n_events must be >= 8")
    dag = EventDAG()
    exogenous = [f"E{i}" for i in range(4)]
    channels = [Channel.TEXT, Channel.TOOL, Channel.MEMORY, Channel.RETRIEVAL]
    for i, eid in enumerate(exogenous):
        dag.add(
            CommunicationEvent(
                event_id=eid,
                sender=f"src{i}",
                receiver="hub0",
                channel=channels[i],
                message=f"clean_{channels[i].value}_{eid}",
                time_index=i,
            )
        )
    # inject one gold fault among exogenous events
    gold = rng.choice(exogenous)
    dag.events[gold] = dag.events[gold].model_copy(
        update={"message": FAULT_BY_CHANNEL[dag.events[gold].channel]}
    )

    prior = list(exogenous)
    for idx in range(4, n_events):
        eid = f"E{idx}"
        n_par = rng.randint(1, min(3, len(prior)))
        parents = sorted(rng.sample(prior, n_par), key=lambda x: int(x[1:]))
        channel = rng.choice(channels)
        dag.add(
            CommunicationEvent(
                event_id=eid,
                sender=f"node{idx}",
                receiver=f"node{idx+1}",
                channel=channel,
                message=f"derived_placeholder_{eid}",
                time_index=idx,
                parents=parents,
            )
        )
        prior.append(eid)
    reward = 0.0 if any("FAULT_" in e.message for e in dag.events.values()) else 1.0
    return RunTrace(
        run_id=f"rand_{seed}_{n_events}",
        task_id="week3_random",
        architecture_id="week3_random_dag",
        dag=dag,
        outcome=RunOutcome(reward=reward, success=reward >= 1.0),
        gold_fault_event_id=gold,
        gold_fault_event_ids=[gold],
        poison_mode="synthetic_random_fault",
    )


def build_random_dataset(*, n_traces: int = 40, n_events: int = 16, seed: int = 7) -> list[RunTrace]:
    return [build_random_trace(seed + i, n_events=n_events) for i in range(n_traces)]
