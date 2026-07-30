"""
Replay Complexity Suite — synthetic DAGs that isolate Exact Replay cost drivers.

Parameters (not merely larger K):
  - branching factor
  - descendant ratio
  - shared subgraphs
  - (via engines) expensive structural evaluations
"""

from __future__ import annotations

from dataclasses import dataclass

from commscm.benchmarks.causal_comm_bench import FAULT_TEXT
from commscm.runtime.mechanisms import MechanismRegistry, descendants_of
from commscm.schema.events import Channel, CommunicationEvent, EventDAG, RunOutcome, RunTrace


@dataclass(frozen=True)
class ReplayComplexitySpec:
    n_events: int
    branching_factor: int
    descendant_ratio: float
    shared_subgraph_frac: float
    seed: int = 0

    def __post_init__(self) -> None:
        if self.n_events < 8:
            raise ValueError("n_events must be >= 8")
        if self.branching_factor < 1:
            raise ValueError("branching_factor must be >= 1")
        if not 0.0 <= self.descendant_ratio <= 1.0:
            raise ValueError("descendant_ratio must be in [0, 1]")
        if not 0.0 <= self.shared_subgraph_frac <= 1.0:
            raise ValueError("shared_subgraph_frac must be in [0, 1]")


# Back-compat alias
BottleneckSpec = ReplayComplexitySpec


def _channel_for(i: int) -> Channel:
    return [Channel.TEXT, Channel.TOOL, Channel.MEMORY, Channel.RETRIEVAL][i % 4]


def build_replay_complexity_trace(spec: ReplayComplexitySpec) -> RunTrace:
    """
    Build a DAG that isolates Exact Replay complexity axes.

    Layout
    ------
    - Intervention root R = E0 (gold fault).
    - Exactly floor(descendant_ratio * (n-1)) nodes are descendants of R.
    - Remaining nodes form a parallel chain (not reachable from R).
    - Branching factor controls fan-out inside the descendant tree.
    - shared_subgraph_frac of descendant nodes get a second parent (diamond /
      shared workflow), relevant for repeated-attribution / cache workloads.
    """
    n = spec.n_events
    n_desc = int(round(spec.descendant_ratio * (n - 1)))
    n_desc = max(0, min(n - 1, n_desc))
    n_parallel = (n - 1) - n_desc

    dag = EventDAG()
    dag.add(
        CommunicationEvent(
            event_id="E0",
            sender="root",
            receiver="hub",
            channel=Channel.TEXT,
            message=FAULT_TEXT,
            time_index=0,
            meta={"role": "intervention_root"},
        )
    )

    parallel_ids: list[str] = []
    if n_parallel > 0:
        seed_id = "P0"
        dag.add(
            CommunicationEvent(
                event_id=seed_id,
                sender="parallel_src",
                receiver="parallel_hub",
                channel=Channel.TOOL,
                message="parallel_exogenous_clean",
                time_index=1,
                meta={"role": "parallel_seed"},
            )
        )
        parallel_ids.append(seed_id)
        t = 2
        prev = seed_id
        while len(parallel_ids) < n_parallel:
            eid = f"P{len(parallel_ids)}"
            dag.add(
                CommunicationEvent(
                    event_id=eid,
                    sender=f"par{len(parallel_ids)}",
                    receiver=f"par{len(parallel_ids)+1}",
                    channel=_channel_for(len(parallel_ids)),
                    message=f"parallel_placeholder_{eid}",
                    time_index=t,
                    parents=[prev],
                    meta={"role": "parallel"},
                )
            )
            parallel_ids.append(eid)
            prev = eid
            t += 1
        next_t = t
    else:
        next_t = 1

    desc_ids: list[str] = []
    frontier: list[str] = ["E0"]
    shared_budget = int(round(spec.shared_subgraph_frac * n_desc))
    shared_used = 0
    t = next_t

    while len(desc_ids) < n_desc:
        if not frontier:
            frontier = ["E0"]
        parent = frontier.pop(0)
        children_made = 0
        while children_made < spec.branching_factor and len(desc_ids) < n_desc:
            eid = f"D{len(desc_ids)}"
            parents = [parent]
            if shared_used < shared_budget and desc_ids:
                second = desc_ids[
                    max(0, len(desc_ids) - 1 - (shared_used % max(1, spec.branching_factor)))
                ]
                if second != parent and second not in parents:
                    parents.append(second)
                    shared_used += 1
            parents = sorted(parents, key=lambda pid: dag.events[pid].time_index)
            dag.add(
                CommunicationEvent(
                    event_id=eid,
                    sender=f"d{len(desc_ids)}",
                    receiver=f"d{len(desc_ids)+1}",
                    channel=_channel_for(len(desc_ids)),
                    message=f"desc_placeholder_{eid}",
                    time_index=t,
                    parents=parents,
                    meta={"role": "descendant", "shared": len(parents) > 1},
                )
            )
            desc_ids.append(eid)
            frontier.append(eid)
            children_made += 1
            t += 1

    mechs = MechanismRegistry()
    messages = {eid: dag.events[eid].message for eid in dag.topological_order()}
    for eid in dag.topological_order():
        ev = dag.events[eid]
        if not ev.parents:
            continue
        parent_msgs = {p: messages[p] for p in ev.parents}
        messages[eid] = mechs.get(eid)(ev, parent_msgs)
        dag.events[eid] = ev.model_copy(update={"message": messages[eid]})

    actual_desc = descendants_of(dag, "E0")
    for eid in desc_ids:
        if eid not in actual_desc:
            raise RuntimeError(f"expected descendant {eid} not reachable from E0")
    for eid in parallel_ids:
        if eid in actual_desc:
            raise RuntimeError(f"parallel node {eid} unexpectedly reachable from E0")

    actual_ratio = len(actual_desc) / (n - 1) if n > 1 else 0.0
    run_id = (
        f"rc_n{n}_b{spec.branching_factor}_d{int(spec.descendant_ratio*100)}"
        f"_s{int(spec.shared_subgraph_frac*100)}_seed{spec.seed}"
    )
    return RunTrace(
        run_id=run_id,
        task_id="week3_replay_complexity",
        architecture_id="replay_complexity_suite_v0",
        dag=dag,
        outcome=RunOutcome(
            reward=0.0,
            success=False,
            metrics={
                "n_events": n,
                "branching_factor": spec.branching_factor,
                "descendant_ratio_target": spec.descendant_ratio,
                "descendant_ratio_actual": round(actual_ratio, 4),
                "n_descendants": len(actual_desc),
                "n_parallel": len(parallel_ids),
                "shared_subgraph_frac": spec.shared_subgraph_frac,
                "shared_nodes": shared_used,
            },
        ),
        gold_fault_event_id="E0",
        gold_fault_event_ids=["E0"],
        poison_mode="replay_complexity",
        extra={
            "intervention_root": "E0",
            "descendant_ids": desc_ids,
            "parallel_ids": parallel_ids,
        },
    )


# Back-compat alias
build_bottleneck_trace = build_replay_complexity_trace


def build_descendant_ratio_suite(
    *,
    n_events: int = 500,
    branching_factor: int = 2,
    ratios: list[float] | None = None,
    shared_subgraph_frac: float = 0.25,
    seed: int = 0,
) -> list[RunTrace]:
    """Fixed-N suite varying only % descendants affected (primary Week-3 experiment)."""
    if ratios is None:
        ratios = [0.1, 0.2, 0.4, 0.6, 0.8, 1.0]
    return [
        build_replay_complexity_trace(
            ReplayComplexitySpec(
                n_events=n_events,
                branching_factor=branching_factor,
                descendant_ratio=r,
                shared_subgraph_frac=shared_subgraph_frac,
                seed=seed,
            )
        )
        for r in ratios
    ]


def build_replay_complexity_grid(
    *,
    n_events_values: list[int] | None = None,
    branching_values: list[int] | None = None,
    descendant_ratios: list[float] | None = None,
    shared_fracs: list[float] | None = None,
    seed: int = 0,
) -> list[RunTrace]:
    """Full factorial grid over replay-complexity axes."""
    n_events_values = n_events_values or [50, 100, 250, 500]
    branching_values = branching_values or [1, 2, 4, 8]
    descendant_ratios = descendant_ratios or [0.1, 0.3, 0.6, 0.9]
    shared_fracs = shared_fracs or [0.0, 0.25, 0.5, 0.75]
    out: list[RunTrace] = []
    for n in n_events_values:
        for b in branching_values:
            for d in descendant_ratios:
                for s in shared_fracs:
                    out.append(
                        build_replay_complexity_trace(
                            ReplayComplexitySpec(
                                n_events=n,
                                branching_factor=b,
                                descendant_ratio=d,
                                shared_subgraph_frac=s,
                                seed=seed,
                            )
                        )
                    )
    return out


build_bottleneck_grid = build_replay_complexity_grid
