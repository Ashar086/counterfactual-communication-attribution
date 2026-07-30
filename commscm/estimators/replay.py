"""Replay primitives: exact oracle, descendant/COW approximations, cost instrumentation."""

from __future__ import annotations

import time
from collections.abc import Iterator, Mapping
from copy import deepcopy
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from commscm.interventions.soft import NullTemplates, SoftIntervention
from commscm.runtime.mechanisms import MechanismRegistry, descendants_of
from commscm.schema.events import CommunicationEvent, EventDAG, RunTrace

# Outcome functions need only `.events` (EventDAG or OverlayEventDAG).
OutcomeFn = Callable[[Any], float]


class CostBreakdown(BaseModel):
    """
    T_total ≈ T_intervention + T_replay + T_evaluation + T_cache

    Within replay, also separate:
      structural_eval_ms  — mechanism / tool / LLM-like work
      materialization_ms  — counterfactual graph construction
    """

    intervention_ms: float = 0.0
    replay_ms: float = 0.0
    structural_eval_ms: float = 0.0
    materialization_ms: float = 0.0
    evaluation_ms: float = 0.0
    cache_ms: float = 0.0
    total_ms: float = 0.0
    structural_evals: int = 0
    materialized_nodes: int = 0
    cache_hits: int = 0
    cache_misses: int = 0

    model_config = {"extra": "forbid"}

    def add(self, other: "CostBreakdown") -> "CostBreakdown":
        return CostBreakdown(
            intervention_ms=self.intervention_ms + other.intervention_ms,
            replay_ms=self.replay_ms + other.replay_ms,
            structural_eval_ms=self.structural_eval_ms + other.structural_eval_ms,
            materialization_ms=self.materialization_ms + other.materialization_ms,
            evaluation_ms=self.evaluation_ms + other.evaluation_ms,
            cache_ms=self.cache_ms + other.cache_ms,
            total_ms=self.total_ms + other.total_ms,
            structural_evals=self.structural_evals + other.structural_evals,
            materialized_nodes=self.materialized_nodes + other.materialized_nodes,
            cache_hits=self.cache_hits + other.cache_hits,
            cache_misses=self.cache_misses + other.cache_misses,
        )


class _OverlayMapping(Mapping[str, CommunicationEvent]):
    """Read-through view: overrides first, else factual events (no full copy)."""

    def __init__(
        self,
        base: dict[str, CommunicationEvent],
        overrides: dict[str, CommunicationEvent],
    ) -> None:
        self._base = base
        self._overrides = overrides

    def __getitem__(self, key: str) -> CommunicationEvent:
        if key in self._overrides:
            return self._overrides[key]
        return self._base[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._base)

    def __len__(self) -> int:
        return len(self._base)

    def values(self) -> Iterator[CommunicationEvent]:  # type: ignore[override]
        for k in self._base:
            yield self[k]

    def items(self) -> Iterator[tuple[str, CommunicationEvent]]:  # type: ignore[override]
        for k in self._base:
            yield k, self[k]


class OverlayEventDAG:
    """
    Copy-on-write counterfactual view.

    Unchanged nodes are referenced from the factual DAG; only intervened and
    recomputed descendant events are materialized.
    """

    def __init__(
        self,
        base: EventDAG,
        overrides: dict[str, CommunicationEvent],
    ) -> None:
        self.base = base
        self.overrides = overrides
        self.events = _OverlayMapping(base.events, overrides)

    def materialize(self) -> EventDAG:
        """Eager full DAG (O(N)); use only when a concrete EventDAG is required."""
        out = EventDAG()
        for eid in self.base.topological_order():
            out.add(self.events[eid].model_copy(deep=True))
        return out


class ReplayResult(BaseModel):
    intervened_event_id: str
    factual_reward: float
    counterfactual_reward: float
    # Full DAG when oracle materializes; None when COW overlay is used.
    counterfactual_dag: EventDAG | None = None
    materialization_mode: str = "full"
    recomputed_event_ids: list[str] = Field(default_factory=list)
    unchanged_event_ids: list[str] = Field(default_factory=list)
    runtime_ms: float = 0.0
    cost: CostBreakdown = Field(default_factory=CostBreakdown)

    _overlay: OverlayEventDAG | None = PrivateAttr(default=None)

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    def counterfactual_view(self) -> EventDAG | OverlayEventDAG:
        if self._overlay is not None:
            return self._overlay
        if self.counterfactual_dag is not None:
            return self.counterfactual_dag
        raise RuntimeError("no counterfactual view available")

    def ensure_counterfactual_dag(self) -> EventDAG:
        if self.counterfactual_dag is not None:
            return self.counterfactual_dag
        if self._overlay is None:
            raise RuntimeError("no overlay to materialize")
        self.counterfactual_dag = self._overlay.materialize()
        return self.counterfactual_dag


def _busy_work(iters: int) -> None:
    """Deterministic CPU burn to simulate expensive structural/tool evaluations."""
    x = 0
    for i in range(iters):
        x = (x * 1664525 + i) & 0xFFFFFFFF
    if x == -1:
        raise RuntimeError("unreachable")


class ReplayEngineBase:
    def __init__(
        self,
        outcome_fn: OutcomeFn,
        mechanisms: MechanismRegistry | None = None,
        nulls: NullTemplates | None = None,
        *,
        structural_cost_iters: int = 0,
        outcome_cost_iters: int = 0,
    ) -> None:
        self.outcome_fn = outcome_fn
        self.mechanisms = mechanisms or MechanismRegistry()
        self.nulls = nulls or NullTemplates()
        self.structural_cost_iters = int(structural_cost_iters)
        self.outcome_cost_iters = int(outcome_cost_iters)

    def factual_reward(self, trace: RunTrace) -> float:
        if self.outcome_cost_iters:
            _busy_work(self.outcome_cost_iters)
        return float(self.outcome_fn(trace.dag))

    def _eval_outcome(self, dag: EventDAG | OverlayEventDAG) -> tuple[float, float]:
        t0 = time.perf_counter()
        if self.outcome_cost_iters:
            _busy_work(self.outcome_cost_iters)
        y = float(self.outcome_fn(dag))
        return y, (time.perf_counter() - t0) * 1000.0

    def _run_mechanism(
        self, event: CommunicationEvent, parent_msgs: dict[str, str]
    ) -> tuple[str, float]:
        t0 = time.perf_counter()
        if self.structural_cost_iters:
            _busy_work(self.structural_cost_iters)
        msg = self.mechanisms.get(event.event_id)(event, parent_msgs)
        return msg, (time.perf_counter() - t0) * 1000.0

    def _resolve_intervention_message(
        self, trace: RunTrace, intervention: SoftIntervention
    ) -> str:
        base = trace.dag.events[intervention.event_id]
        if intervention.new_message is not None:
            return intervention.new_message
        if intervention.use_channel_null:
            tmpl = intervention.nulls if intervention.nulls else self.nulls
            return tmpl.for_channel(base.channel)
        raise ValueError("new_message required when use_channel_null=False")

    def replay(self, trace: RunTrace, intervention: SoftIntervention) -> ReplayResult:
        raise NotImplementedError


def _make_event(
    factual: CommunicationEvent,
    *,
    message: str,
    meta: dict[str, Any],
) -> CommunicationEvent:
    return CommunicationEvent(
        event_id=factual.event_id,
        sender=factual.sender,
        receiver=factual.receiver,
        channel=factual.channel,
        message=message,
        time_index=factual.time_index,
        parents=list(factual.parents),
        meta=meta,
    )


class FullReplayEngine(ReplayEngineBase):
    """Oracle: recompute every parentful/mechanized node; full DAG materialization."""

    def replay(self, trace: RunTrace, intervention: SoftIntervention) -> ReplayResult:
        t_all = time.perf_counter()
        dag = trace.dag
        eid = intervention.event_id
        if eid not in dag.events:
            raise KeyError(f"unknown event_id: {eid}")

        t0 = time.perf_counter()
        factual_y, eval_ms_f = self._eval_outcome(dag)
        new_msg = self._resolve_intervention_message(trace, intervention)
        intervention_ms = (time.perf_counter() - t0) * 1000.0

        t_replay = time.perf_counter()
        cf = EventDAG()
        recomputed: list[str] = []
        unchanged: list[str] = []
        messages: dict[str, str] = {}
        structural_ms = 0.0
        materialization_ms = 0.0
        structural_evals = 0

        for nid in dag.topological_order():
            factual = dag.events[nid]
            meta = deepcopy(factual.meta)
            if nid == eid:
                meta["intervention"] = {
                    "tag": intervention.tag,
                    "original_message_preview": factual.message[:200],
                    "channel": factual.channel.value,
                }
                msg = new_msg
                recomputed.append(nid)
            elif factual.parents:
                parent_msgs = {p: messages[p] for p in factual.parents}
                msg, dt = self._run_mechanism(factual, parent_msgs)
                structural_ms += dt
                structural_evals += 1
                meta["recomputed"] = True
                recomputed.append(nid)
            else:
                msg = factual.message
                unchanged.append(nid)
            messages[nid] = msg
            t_mat = time.perf_counter()
            cf.add(_make_event(factual, message=msg, meta=meta))
            materialization_ms += (time.perf_counter() - t_mat) * 1000.0

        replay_ms = (time.perf_counter() - t_replay) * 1000.0
        y_cf, eval_ms_cf = self._eval_outcome(cf)
        evaluation_ms = eval_ms_f + eval_ms_cf
        total_ms = (time.perf_counter() - t_all) * 1000.0
        cost = CostBreakdown(
            intervention_ms=round(intervention_ms, 3),
            replay_ms=round(replay_ms, 3),
            structural_eval_ms=round(structural_ms, 3),
            materialization_ms=round(materialization_ms, 3),
            evaluation_ms=round(evaluation_ms, 3),
            cache_ms=0.0,
            total_ms=round(total_ms, 3),
            structural_evals=structural_evals,
            materialized_nodes=len(cf.events),
        )
        return ReplayResult(
            intervened_event_id=eid,
            factual_reward=factual_y,
            counterfactual_reward=y_cf,
            counterfactual_dag=cf,
            materialization_mode="full",
            recomputed_event_ids=recomputed,
            unchanged_event_ids=unchanged,
            runtime_ms=round(total_ms, 3),
            cost=cost,
        )


class DescendantReplayEngine(ReplayEngineBase):
    """
    Descendant replay with copy-on-write / subgraph-only materialization.

    Structural evaluations: only intervention + descendants.
    Materialization: only override nodes (not O(N) full DAG copy).
    """

    def replay(self, trace: RunTrace, intervention: SoftIntervention) -> ReplayResult:
        t_all = time.perf_counter()
        dag = trace.dag
        eid = intervention.event_id
        if eid not in dag.events:
            raise KeyError(f"unknown event_id: {eid}")

        t0 = time.perf_counter()
        factual_y, eval_ms_f = self._eval_outcome(dag)
        desc = descendants_of(dag, eid)
        affected = {eid, *desc}
        new_msg = self._resolve_intervention_message(trace, intervention)
        intervention_ms = (time.perf_counter() - t0) * 1000.0

        t_replay = time.perf_counter()
        overrides: dict[str, CommunicationEvent] = {}
        messages: dict[str, str] = {}
        recomputed: list[str] = []
        structural_ms = 0.0
        materialization_ms = 0.0
        structural_evals = 0

        # Schema enforces parent.time_index <= child.time_index, so sorting the
        # affected set by time_index is a valid topological order — O(|A| log |A|)
        # instead of a full O(N) DAG topo for every intervention.
        affected_order = sorted(affected, key=lambda i: dag.events[i].time_index)
        for nid in affected_order:
            factual = dag.events[nid]
            meta = deepcopy(factual.meta)
            if nid == eid:
                meta["intervention"] = {
                    "tag": intervention.tag,
                    "original_message_preview": factual.message[:200],
                    "channel": factual.channel.value,
                }
                msg = new_msg
                recomputed.append(nid)
            elif factual.parents:
                parent_msgs = {
                    p: messages[p] if p in messages else dag.events[p].message
                    for p in factual.parents
                }
                msg, dt = self._run_mechanism(factual, parent_msgs)
                structural_ms += dt
                structural_evals += 1
                meta["recomputed"] = True
                recomputed.append(nid)
            else:
                msg = factual.message
                recomputed.append(nid)
            messages[nid] = msg
            t_mat = time.perf_counter()
            overrides[nid] = _make_event(factual, message=msg, meta=meta)
            materialization_ms += (time.perf_counter() - t_mat) * 1000.0

        overlay = OverlayEventDAG(dag, overrides)
        # Unchanged nodes are implicit (base DAG references); avoid O(N) listing.
        unchanged: list[str] = []

        replay_ms = (time.perf_counter() - t_replay) * 1000.0
        y_cf, eval_ms_cf = self._eval_outcome(overlay)
        evaluation_ms = eval_ms_f + eval_ms_cf
        total_ms = (time.perf_counter() - t_all) * 1000.0
        cost = CostBreakdown(
            intervention_ms=round(intervention_ms, 3),
            replay_ms=round(replay_ms, 3),
            structural_eval_ms=round(structural_ms, 3),
            materialization_ms=round(materialization_ms, 3),
            evaluation_ms=round(evaluation_ms, 3),
            cache_ms=0.0,
            total_ms=round(total_ms, 3),
            structural_evals=structural_evals,
            materialized_nodes=len(overrides),
        )
        result = ReplayResult(
            intervened_event_id=eid,
            factual_reward=factual_y,
            counterfactual_reward=y_cf,
            counterfactual_dag=None,
            materialization_mode="cow_overlay",
            recomputed_event_ids=recomputed,
            unchanged_event_ids=unchanged,
            runtime_ms=round(total_ms, 3),
            cost=cost,
        )
        result._overlay = overlay
        return result


class CachedDescendantReplayEngine(DescendantReplayEngine):
    """
    Descendant COW replay + memoized results for repeated attribution workloads
    (many interventions / repeated queries on the same factual trace).
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cache: dict[tuple[str, str, str], ReplayResult] = {}

    def replay(self, trace: RunTrace, intervention: SoftIntervention) -> ReplayResult:
        t_cache = time.perf_counter()
        factual_key = trace.run_id
        new_msg = self._resolve_intervention_message(trace, intervention)
        key = (factual_key, intervention.event_id, new_msg)
        if key in self._cache:
            hit = self._cache[key]
            # Shallow reuse of immutable-enough fields; rebuild thin result.
            cache_ms = (time.perf_counter() - t_cache) * 1000.0
            out = ReplayResult(
                intervened_event_id=hit.intervened_event_id,
                factual_reward=hit.factual_reward,
                counterfactual_reward=hit.counterfactual_reward,
                counterfactual_dag=None,
                materialization_mode=hit.materialization_mode,
                recomputed_event_ids=list(hit.recomputed_event_ids),
                unchanged_event_ids=list(hit.unchanged_event_ids),
                runtime_ms=round(cache_ms, 3),
                cost=CostBreakdown(
                    cache_ms=round(cache_ms, 3),
                    total_ms=round(cache_ms, 3),
                    cache_hits=1,
                ),
            )
            out._overlay = hit._overlay
            return out
        cache_lookup_ms = (time.perf_counter() - t_cache) * 1000.0
        result = super().replay(trace, intervention)
        result.cost.cache_ms = round(result.cost.cache_ms + cache_lookup_ms, 3)
        result.cost.cache_misses = 1
        result.cost.total_ms = round(result.cost.total_ms + cache_lookup_ms, 3)
        result.runtime_ms = result.cost.total_ms
        self._cache[key] = result
        return result


def fault_marker_outcome(dag: EventDAG | OverlayEventDAG) -> float:
    for e in dag.events.values():
        if e.message.startswith("FAULT_") or "FAULT_" in e.message:
            return 0.0
    return 1.0
