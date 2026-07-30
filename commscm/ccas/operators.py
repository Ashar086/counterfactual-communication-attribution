"""
Phase A ArchitectureOperators: ranked proposals only (no graph mutation).

Methods for H1:
  - CR-guided: scores edges from AttributionReport ΔY
  - Reward-only: surface/heuristic scores (no counterfactual CR)
  - Random: uniform edge ranking
"""

from __future__ import annotations

import random
from typing import Iterable

from commscm.attribution.report import AttributionReport
from commscm.ccas.interfaces import (
    ArchitectureEdit,
    ArchitectureEditKind,
    ArchitectureProposal,
)
from commscm.schema.events import RunTrace


def dag_edges(trace: RunTrace) -> list[tuple[str, str]]:
    """Directed edges (parent → child) in the factual event DAG."""
    edges: list[tuple[str, str]] = []
    for eid, ev in trace.dag.events.items():
        for p in ev.parents:
            edges.append((p, eid))
    return edges


def gold_harmful_edges(trace: RunTrace) -> set[tuple[str, str]]:
    """
    Gold harmful pathways for H1: edges incident to gold fault event(s).

    (parent → gold) and (gold → child).
    """
    golds = set(trace.gold_fault_event_ids)
    if trace.gold_fault_event_id:
        golds.add(trace.gold_fault_event_id)
    harmful: set[tuple[str, str]] = set()
    for eid, ev in trace.dag.events.items():
        for p in ev.parents:
            if p in golds or eid in golds:
                harmful.add((p, eid))
    return harmful


class _PhaseABase:
    """Shared Phase-A apply: no mutation."""

    name: str = "phase_a"

    def apply(self, architecture_id: str, proposal: ArchitectureProposal) -> str:
        # Phase A/B gate: ranking only until H1 passes and Phase B begins.
        return architecture_id

    def _proposal(
        self,
        trace: RunTrace,
        ranked_edits: list[ArchitectureEdit],
        motivating: list[str],
        *,
        method: str,
    ) -> ArchitectureProposal:
        return ArchitectureProposal(
            proposal_id=f"{method}_{trace.run_id}",
            base_architecture_id=trace.architecture_id,
            edits=ranked_edits,
            motivating_event_ids=motivating,
            expected_utility=None,
            meta={"phase": "A", "method": method, "mutation": False},
        )

    @staticmethod
    def _expand_edge_edits(
        edges_scored: list[tuple[float, str, str]],
    ) -> list[ArchitectureEdit]:
        """
        For each edge (high score first), emit prune > weaken > insert_verifier
        with slightly decaying scores so prune of the top edge ranks first.
        """
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
        scored.sort(key=lambda t: (-t[0], t[1].kind.value, t[1].source_event_id or "", t[1].target_event_id or ""))
        return [e for _, e in scored]


class CRGuidedOperator(_PhaseABase):
    """Rank edits using Communication Responsibility (ΔY) from AttributionReport."""

    name = "cr_guided"

    def propose(self, trace: RunTrace, report: AttributionReport) -> ArchitectureProposal:
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


class RewardOnlyOperator(_PhaseABase):
    """
    Reward/heuristic-only baseline: no counterfactual CR and no fault-label leakage.

    Deliberately ignores AttributionReport ΔY and does not inspect FAULT_ markers.
    Under failure, ranks edges by sink proximity (later time_index) only.
    """

    name = "reward_only"

    def propose(self, trace: RunTrace, report: AttributionReport) -> ArchitectureProposal:
        n = max(len(trace.dag.events), 1)
        event_score: dict[str, float] = {}
        for eid, ev in trace.dag.events.items():
            if report.factual_reward < 1.0:
                # Weak failure heuristic: blame later nodes (near sink).
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


class RandomOperator(_PhaseABase):
    """Uniform random ranking of edges (seeded)."""

    name = "random"

    def __init__(self, seed: int = 0) -> None:
        self.seed = seed

    def propose(self, trace: RunTrace, report: AttributionReport) -> ArchitectureProposal:
        edges = list(dag_edges(trace))
        rng = random.Random(self.seed ^ hash(trace.run_id) & 0xFFFFFFFF)
        rng.shuffle(edges)
        # Assign descending fake scores for stable expand ordering.
        scored = [(float(len(edges) - i), src, tgt) for i, (src, tgt) in enumerate(edges)]
        edits = self._expand_edge_edits(scored)
        return self._proposal(trace, edits, [], method=self.name)


def unique_edges_in_order(edits: Iterable[ArchitectureEdit]) -> list[tuple[str, str]]:
    """Deduplicate (src,tgt) preserving first occurrence (kind-agnostic ranking)."""
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
