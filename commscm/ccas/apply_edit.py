"""
Phase B: apply a single architecture edit to an event DAG.

No iterative optimization — one edit from a proposal, then stop.
"""

from __future__ import annotations

from copy import deepcopy

from pydantic import BaseModel

from commscm.ccas.interfaces import ArchitectureEdit, ArchitectureEditKind, ArchitectureProposal
from commscm.interventions.soft import NullTemplates
from commscm.runtime.mechanisms import MechanismRegistry
from commscm.schema.events import CommunicationEvent, EventDAG, RunOutcome, RunTrace


class ApplyEditResult(BaseModel):
    architecture_id: str
    edit: ArchitectureEdit
    dag: EventDAG
    trace: RunTrace | None = None

    model_config = {"arbitrary_types_allowed": True, "extra": "forbid"}


def _copy_dag(dag: EventDAG) -> EventDAG:
    out = EventDAG()
    for eid in dag.topological_order():
        out.add(dag.events[eid].model_copy(deep=True))
    return out


def rematerialize(dag: EventDAG, mechanisms: MechanismRegistry | None = None) -> EventDAG:
    """Recompute mechanized node messages after topology/meta changes."""
    mechs = mechanisms or MechanismRegistry()
    messages: dict[str, str] = {}
    out = EventDAG()
    for eid in dag.topological_order():
        ev = dag.events[eid]
        meta = deepcopy(ev.meta)
        weakened = set(meta.get("weakened_parents", []) or [])
        if not ev.parents:
            # After prune-to-exogenous, drop stale derived/FAULT payloads.
            if (meta.get("architecture_edit") or {}).get("kind") == "prune_edge":
                msg = f"clean_exogenous_after_prune:{eid}"
            else:
                msg = ev.message
        else:
            parent_msgs = {}
            for p in ev.parents:
                raw = messages[p]
                if p in weakened:
                    raw = NullTemplates().for_channel(ev.channel)
                parent_msgs[p] = raw
            # Verifier nodes: pass cleaned parent text
            if meta.get("role") == "verifier":
                src = ev.parents[0]
                src_msg = messages[src]
                if "FAULT_" in src_msg:
                    msg = NullTemplates().for_channel(ev.channel)
                else:
                    msg = f"[VERIFIED] {src_msg}"
                meta["verified"] = True
            else:
                msg = mechs.get(eid)(ev, parent_msgs)
        messages[eid] = msg
        out.add(ev.model_copy(update={"message": msg, "meta": meta}, deep=True))
    return out


def apply_single_edit(
    dag: EventDAG,
    edit: ArchitectureEdit,
    *,
    mechanisms: MechanismRegistry | None = None,
) -> EventDAG:
    """
    Apply exactly one architecture edit and rematerialize messages.

    - prune_edge (src→tgt): remove src from tgt.parents
    - weaken_edge (src→tgt): keep edge; mark src as weakened for tgt
    - insert_verifier (src→tgt): insert verifier node between src and tgt
    - no_op / unsupported: return rematerialized copy unchanged topologically
    """
    if edit.kind == ArchitectureEditKind.NO_OP:
        return rematerialize(_copy_dag(dag), mechanisms)

    src, tgt = edit.source_event_id, edit.target_event_id
    if edit.kind in (
        ArchitectureEditKind.PRUNE_EDGE,
        ArchitectureEditKind.WEAKEN_EDGE,
        ArchitectureEditKind.INSERT_VERIFIER,
    ):
        if not src or not tgt:
            raise ValueError(f"{edit.kind} requires source_event_id and target_event_id")
        if tgt not in dag.events or src not in dag.events:
            raise KeyError(f"edit endpoints missing: {src!r} → {tgt!r}")
        if src not in dag.events[tgt].parents:
            raise ValueError(f"edge {src!r}→{tgt!r} not present")

    base = _copy_dag(dag)

    if edit.kind == ArchitectureEditKind.PRUNE_EDGE:
        assert src and tgt
        child = base.events[tgt]
        new_parents = [p for p in child.parents if p != src]
        meta = deepcopy(child.meta)
        meta["architecture_edit"] = {"kind": "prune_edge", "removed_parent": src}
        base.events[tgt] = child.model_copy(update={"parents": new_parents, "meta": meta})
        return rematerialize(base, mechanisms)

    if edit.kind == ArchitectureEditKind.WEAKEN_EDGE:
        assert src and tgt
        child = base.events[tgt]
        meta = deepcopy(child.meta)
        weakened = list(meta.get("weakened_parents", []) or [])
        if src not in weakened:
            weakened.append(src)
        meta["weakened_parents"] = weakened
        meta["architecture_edit"] = {"kind": "weaken_edge", "parent": src}
        base.events[tgt] = child.model_copy(update={"meta": meta})
        return rematerialize(base, mechanisms)

    if edit.kind == ArchitectureEditKind.INSERT_VERIFIER:
        assert src and tgt
        child = base.events[tgt]
        parent = base.events[src]
        # time_index strictly between parent and child
        v_time = parent.time_index
        # Ensure uniqueness: use fractional-free int slot — shift if needed by using
        # max(parent.time_index, child.time_index - 1) pattern with new id.
        # Schema requires parent.time <= child.time; insert with time = parent.time
        # and bump child if equal — rebuild with verifier at parent.time_index
        # and child kept; if parent.time_index == child.time_index (shouldn't), bump child.
        vid = f"V_{src}_{tgt}"
        if vid in base.events:
            vid = f"V_{src}_{tgt}_{len(base.events)}"
        v_time = parent.time_index
        # Child must have time_index >= verifier. If child.time == parent.time, illegal;
        # our benches use strict increases along paths.
        if child.time_index <= v_time:
            raise ValueError("cannot insert verifier: child time_index not after parent")
        verifier = CommunicationEvent(
            event_id=vid,
            sender="verifier",
            receiver=child.receiver,
            channel=parent.channel,
            message="[VERIFIER_PLACEHOLDER]",
            time_index=v_time,  # same as parent OK if child is later; parents of V = [src]
            parents=[src],
            meta={"role": "verifier", "architecture_edit": {"kind": "insert_verifier", "covers": [src, tgt]}},
        )
        # Rebuild DAG in topo order with verifier inserted and child rewired.
        new_parents = [vid if p == src else p for p in child.parents]
        rebuilt = EventDAG()
        for eid in base.topological_order():
            if eid == tgt:
                # add verifier just before child (verifier's parent src already in rebuilt)
                if vid not in rebuilt.events:
                    # verifier time_index must be >= src; use src.time_index (already set)
                    # but EventDAG forbids parent time > event time — src.time <= v_time OK
                    # child.time > v_time required. If v_time == src.time_index, OK.
                    rebuilt.add(verifier)
                ch = base.events[tgt]
                meta = deepcopy(ch.meta)
                meta["architecture_edit"] = {
                    "kind": "insert_verifier",
                    "verifier_id": vid,
                    "replaced_parent": src,
                }
                rebuilt.add(ch.model_copy(update={"parents": new_parents, "meta": meta}))
            else:
                rebuilt.add(base.events[eid].model_copy(deep=True))
        if vid not in rebuilt.events:
            # tgt was never reached? shouldn't happen
            rebuilt.add(verifier)
        return rematerialize(rebuilt, mechanisms)

    if edit.kind == ArchitectureEditKind.REROUTE_CHANNEL:
        # Phase B: treat as no-op topology change (reserved for later).
        return rematerialize(base, mechanisms)

    raise ValueError(f"unsupported edit kind: {edit.kind}")


def apply_edit_to_trace(
    trace: RunTrace,
    edit: ArchitectureEdit,
    *,
    mechanisms: MechanismRegistry | None = None,
    outcome_fn=None,
    new_architecture_id: str | None = None,
) -> RunTrace:
    """Return a new RunTrace after one edit (Phase B)."""
    from commscm.estimators.replay import fault_marker_outcome

    y_fn = outcome_fn or fault_marker_outcome
    new_dag = apply_single_edit(trace.dag, edit, mechanisms=mechanisms)
    reward = float(y_fn(new_dag))
    arch_id = new_architecture_id or (
        f"{trace.architecture_id}__{edit.kind.value}__"
        f"{edit.source_event_id}_{edit.target_event_id}"
    )
    return trace.model_copy(
        update={
            "run_id": f"{trace.run_id}__edit_{edit.kind.value}",
            "architecture_id": arch_id,
            "dag": new_dag,
            "outcome": RunOutcome(reward=reward, success=reward >= 1.0),
            "extra": {
                **trace.extra,
                "phase_b_edit": edit.model_dump(mode="json"),
                "base_run_id": trace.run_id,
            },
        },
        deep=True,
    )


class ArchitectureRegistry:
    """
    Stores architecture DAG templates. Operator.apply returns a new architecture id
    after applying the proposal's **first** edit only (Phase B).
    """

    def __init__(self) -> None:
        self._dags: dict[str, EventDAG] = {}
        self._meta: dict[str, dict] = {}

    def register(self, architecture_id: str, dag: EventDAG) -> None:
        self._dags[architecture_id] = _copy_dag(dag)
        self._meta[architecture_id] = {"edits": []}

    def contains(self, architecture_id: str) -> bool:
        return architecture_id in self._dags

    def get(self, architecture_id: str) -> EventDAG:
        if architecture_id not in self._dags:
            raise KeyError(architecture_id)
        return _copy_dag(self._dags[architecture_id])

    def apply_proposal(
        self,
        architecture_id: str,
        proposal: ArchitectureProposal,
        *,
        mechanisms: MechanismRegistry | None = None,
    ) -> str:
        if not proposal.edits:
            return architecture_id
        edit = proposal.edits[0]  # Phase B: single edit only
        if edit.kind == ArchitectureEditKind.NO_OP:
            return architecture_id
        base = self.get(architecture_id)
        new_dag = apply_single_edit(base, edit, mechanisms=mechanisms)
        new_id = (
            f"{architecture_id}__{edit.kind.value}__"
            f"{edit.source_event_id}_{edit.target_event_id}"
        )
        # uniquify if collision
        if new_id in self._dags:
            new_id = f"{new_id}__{len(self._dags)}"
        self._dags[new_id] = new_dag
        self._meta[new_id] = {
            "base": architecture_id,
            "edits": [edit.model_dump(mode="json")],
            "proposal_id": proposal.proposal_id,
        }
        return new_id
