"""
Phase D: iterative CCAS loop — budgeted propose → apply top-1 → re-attribute.

H2-lite: does CR-guided search repair with fewer edits than reward-only/random?
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from commscm.attribution.engines import DescendantReplayEstimator
from commscm.ccas.apply_edit import apply_edit_to_trace
from commscm.ccas.interfaces import ArchitectureEdit, ArchitectureEditKind
from commscm.ccas.operators import (
    CRGuidedOperator,
    PhaseBOperatorBase,
    RandomOperator,
    RewardOnlyOperator,
    sink_fault_outcome,
)
from commscm.estimators.replay import DescendantReplayEngine, fault_marker_outcome
from commscm.runtime.mechanisms import MechanismRegistry
from commscm.schema.events import RunOutcome, RunTrace


class CCASStep(BaseModel):
    step: int
    edit: ArchitectureEdit
    y_before: float
    y_after: float

    model_config = {"extra": "forbid"}


class CCASResult(BaseModel):
    method: str
    run_id: str
    success: bool
    n_edits: int
    edit_budget: int
    y_initial: float
    y_final: float
    steps: list[CCASStep] = Field(default_factory=list)
    gold_edges_hit: int = 0
    gold_edges_total: int = 0

    model_config = {"extra": "forbid"}


def _gold_edge_set(trace: RunTrace) -> set[tuple[str, str]]:
    raw = trace.extra.get("gold_harmful_edges") or []
    out: set[tuple[str, str]] = set()
    for e in raw:
        if isinstance(e, (list, tuple)) and len(e) == 2:
            out.add((str(e[0]), str(e[1])))
    return out


def _terminal_ids(dag: EventDAG) -> list[str]:
    sinks = [eid for eid in dag.events if not dag.children(eid)]
    if not sinks:
        return list(dag.events)
    max_t = max(dag.events[s].time_index for s in sinks)
    return [s for s in sinks if dag.events[s].time_index == max_t]


def _preserves_terminal_attachment(dag: EventDAG) -> bool:
    return all(dag.events[t].parents for t in _terminal_ids(dag))


class CCASLoop:
    """
    Iterative communication-attribution architecture search (minimal).

    Each iteration:
      1. Score current trace (Descendant attribution; Part II frozen)
      2. Propose ranked edits
      3. Apply the first *prune_edge* that preserves terminal-sink attachment
         (H2-lite isolates pathway removal; verifier inserts are reserved for H3)
      4. Stop on terminal-sink success or budget exhaustion
    """

    def __init__(
        self,
        operator: PhaseBOperatorBase,
        *,
        edit_budget: int = 4,
        attr_engine: DescendantReplayEstimator | None = None,
        prune_only: bool = True,
    ) -> None:
        if edit_budget < 1:
            raise ValueError("edit_budget must be >= 1")
        self.operator = operator
        self.edit_budget = edit_budget
        self.prune_only = prune_only
        self.attr = attr_engine or DescendantReplayEstimator(
            DescendantReplayEngine(
                fault_marker_outcome, MechanismRegistry(), structural_cost_iters=0
            )
        )

    def run(self, trace: RunTrace) -> CCASResult:
        current = trace.model_copy(deep=True)
        y = sink_fault_outcome(current.dag)
        current = current.model_copy(
            update={"outcome": RunOutcome(reward=y, success=y >= 1.0)},
            deep=True,
        )
        gold = _gold_edge_set(current)
        steps: list[CCASStep] = []
        hit = 0
        y0 = y
        self.operator.ensure_registered(current, refresh=True)

        for step_i in range(1, self.edit_budget + 1):
            if y >= 1.0:
                break
            report = self.attr.score(current)
            proposal = self.operator.propose(current, report)
            if not proposal.edits:
                break
            y_before = y
            applied = None
            for edit in proposal.edits:
                if self.prune_only and edit.kind != ArchitectureEditKind.PRUNE_EDGE:
                    continue
                candidate = apply_edit_to_trace(
                    current, edit, outcome_fn=sink_fault_outcome
                )
                if not _preserves_terminal_attachment(candidate.dag):
                    continue
                applied = (edit, candidate)
                break
            if applied is None:
                break
            edit, updated = applied
            current = updated.model_copy(
                update={
                    "run_id": trace.run_id,
                    "architecture_id": trace.architecture_id,
                },
                deep=True,
            )
            self.operator.ensure_registered(current, refresh=True)
            y = float(current.outcome.reward)
            edge = (edit.source_event_id, edit.target_event_id)
            if edge in gold:
                hit += 1
            steps.append(
                CCASStep(step=step_i, edit=edit, y_before=y_before, y_after=y)
            )

        return CCASResult(
            method=getattr(self.operator, "name", "unknown"),
            run_id=trace.run_id,
            success=y >= 1.0,
            n_edits=len(steps),
            edit_budget=self.edit_budget,
            y_initial=y0,
            y_final=y,
            steps=steps,
            gold_edges_hit=hit,
            gold_edges_total=len(gold),
        )


def make_operator(method: str, seed: int = 0) -> PhaseBOperatorBase:
    if method == "cr_guided":
        return CRGuidedOperator()
    if method == "reward_only":
        return RewardOnlyOperator()
    if method == "random":
        return RandomOperator(seed=seed)
    raise ValueError(f"unknown method: {method}")
