"""
Phase B ArchitectureOperators: propose (Phase A) + apply single edit.

apply() uses ArchitectureRegistry and commits only proposal.edits[0].
"""

from __future__ import annotations

import random
from typing import Iterable

from commscm.attribution.report import AttributionReport
from commscm.ccas.apply_edit import ArchitectureRegistry
from commscm.ccas.interfaces import (
    ArchitectureEdit,
    ArchitectureEditKind,
    ArchitectureProposal,
)
from commscm.schema.events import EventDAG, RunTrace


def dag_edges(trace: RunTrace) -> list[tuple[str, str]]:
    """Directed edges (parent → child) in the factual event DAG."""
    edges: list[tuple[str, str]] = []
    for eid, ev in trace.dag.events.items():
        for p in ev.parents:
            edges.append((p, eid))
    return edges


def gold_harmful_edges(trace: RunTrace) -> set[tuple[str, str]]:
    """Gold harmful pathways: edges incident to gold fault event(s)."""
    golds = set(trace.gold_fault_event_ids)
    if trace.gold_fault_event_id:
        golds.add(trace.gold_fault_event_id)
    harmful: set[tuple[str, str]] = set()
    for eid, ev in trace.dag.events.items():
        for p in ev.parents:
            if p in golds or eid in golds:
                harmful.add((p, eid))
    return harmful


def sink_fault_outcome(dag: EventDAG) -> float:
    """
    Phase-B task proxy: success iff the terminal sink(s) have no FAULT_.

    Terminal = events with no children at the maximum time_index (task output).
    Isolated pruned roots that still carry FAULT_ are not counted as task failure.
    """
    sinks = [eid for eid in dag.events if not dag.children(eid)]
    if not sinks:
        sinks = list(dag.events)
    max_t = max(dag.events[s].time_index for s in sinks)
    terminal = [s for s in sinks if dag.events[s].time_index == max_t]
    for eid in terminal:
        if "FAULT_" in dag.events[eid].message:
            return 0.0
    return 1.0


def architecture_key(trace: RunTrace) -> str:
    """Per-trace architecture key (templates may share architecture_id)."""
    return f"{trace.architecture_id}::{trace.run_id}"


class PhaseBOperatorBase:
    """Propose ranked edits; apply only the top edit via a shared registry."""

    name: str = "phase_b"

    def __init__(self, registry: ArchitectureRegistry | None = None) -> None:
        self.registry = registry if registry is not None else ArchitectureRegistry()

    def apply(self, architecture_id: str, proposal: ArchitectureProposal) -> str:
        return self.registry.apply_proposal(architecture_id, proposal)

    def ensure_registered(self, trace: RunTrace) -> str:
        key = architecture_key(trace)
        if not self.registry.contains(key):
            self.registry.register(key, trace.dag)
        return key

    def _proposal(
        self,
        trace: RunTrace,
        ranked_edits: list[ArchitectureEdit],
        motivating: list[str],
        *,
        method: str,
    ) -> ArchitectureProposal:
        key = architecture_key(trace)
        return ArchitectureProposal(
            proposal_id=f"{method}_{trace.run_id}",
            base_architecture_id=key,
            edits=ranked_edits,
            motivating_event_ids=motivating,
            expected_utility=None,
            meta={"phase": "B", "method": method, "mutation": True, "apply_top1_only": True},
        )

    @staticmethod
    def _expand_edge_edits(
        edges_scored: list[tuple[float, str, str]],
    ) -> list[ArchitectureEdit]:
        kinds = (
            (ArchitectureEditKind.PRUNE_EDGE, 1.0),
            (ArchitectureEditKind.WEAKEN_EDGE, 0.95),
            (ArchitectureEditKind.INSERT_VERIFIER, 0.90),
        )
        scored: list[tuple[float, ArchitectureEdit]] = []
        for edge_score, src, tgt in edges_scored:
            for kind, mult in kinds:
                scored.append(
                    (
                        edge_score * mult,
                        ArchitectureEdit(
                            kind=kind,
                            source_event_id=src,
                            target_event_id=tgt,
                            params={"edge_score": edge_score},
                        ),
                    )
                )
        scored.sort(
            key=lambda t: (
                -t[0],
                t[1].kind.value,
                t[1].source_event_id or "",
                t[1].target_event_id or "",
            )
        )
        return [e for _, e in scored]


class CRGuidedOperator(PhaseBOperatorBase):
    name = "cr_guided"

    def propose(self, trace: RunTrace, report: AttributionReport) -> ArchitectureProposal:
        self.ensure_registered(trace)
        delta = {r.event_id: r.delta_y for r in report.rows}
        edges = dag_edges(trace)
        scored = [
            (float(delta.get(src, 0.0)) + float(delta.get(tgt, 0.0)), src, tgt)
            for src, tgt in edges
        ]
        scored.sort(key=lambda t: (-t[0], t[1], t[2]))
        edits = self._expand_edge_edits(scored)
        motivating = [r.event_id for r in report.rows[:5]]
        return self._proposal(trace, edits, motivating, method=self.name)


class RewardOnlyOperator(PhaseBOperatorBase):
    """Reward/heuristic-only: sink proximity under failure; no CR; no FAULT_ leakage."""

    name = "reward_only"

    def propose(self, trace: RunTrace, report: AttributionReport) -> ArchitectureProposal:
        self.ensure_registered(trace)
        n = max(len(trace.dag.events), 1)
        event_score: dict[str, float] = {}
        for eid, ev in trace.dag.events.items():
            if report.factual_reward < 1.0:
                event_score[eid] = float(ev.time_index) / n
            else:
                event_score[eid] = 0.0
        edges = dag_edges(trace)
        scored = [
            (event_score.get(src, 0.0) + event_score.get(tgt, 0.0), src, tgt)
            for src, tgt in edges
        ]
        scored.sort(key=lambda t: (-t[0], t[1], t[2]))
        edits = self._expand_edge_edits(scored)
        motivating = sorted(event_score, key=lambda e: (-event_score[e], e))[:5]
        return self._proposal(trace, edits, motivating, method=self.name)


class RandomOperator(PhaseBOperatorBase):
    name = "random"

    def __init__(self, seed: int = 0, registry: ArchitectureRegistry | None = None) -> None:
        super().__init__(registry=registry)
        self.seed = seed

    def propose(self, trace: RunTrace, report: AttributionReport) -> ArchitectureProposal:
        self.ensure_registered(trace)
        edges = list(dag_edges(trace))
        rng = random.Random(self.seed ^ (hash(trace.run_id) & 0xFFFFFFFF))
        rng.shuffle(edges)
        scored = [(float(len(edges) - i), src, tgt) for i, (src, tgt) in enumerate(edges)]
        edits = self._expand_edge_edits(scored)
        return self._proposal(trace, edits, [], method=self.name)


def unique_edges_in_order(edits: Iterable[ArchitectureEdit]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for e in edits:
        if e.source_event_id is None or e.target_event_id is None:
            continue
        key = (e.source_event_id, e.target_event_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out
