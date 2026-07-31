"""
Live LangGraph edge interventions for Week 6 (Part IV adapter only).

Maps CommSCM prune_edge / weaken_edge onto consumer input gating.
Does not change IF-C-SCM, CR, replay, or CCAS ranking.

Attribution space vs action space
---------------------------------
- Attribution may score *all* events, including exogenous roots (e.g. C0).
- Architecture *actions* apply only to controllable agent↔agent edges.
  Exogenous C0→* edges are skipped when selecting a live edit.
"""

from __future__ import annotations

from typing import Any, Literal

from commscm.ccas.interfaces import ArchitectureEdit, ArchitectureEditKind
from commscm.interventions.soft import NullTemplates
from commscm.schema.events import Channel

EditKindLive = Literal["prune_edge", "weaken_edge"]

# Soft null for TEXT-channel parent payloads (matches Part I soft do)
_NULL_TEXT = NullTemplates().for_channel(Channel.TEXT)

# CommSCM event edge → (consumer_node, parent_field)
# Topology: C0→C1→C2→C3→C4→C5 with extra C2→C4
LIVE_EDGE_MAP: dict[tuple[str, str], tuple[str, str]] = {
    ("C0", "C1"): ("planner", "task_description"),
    ("C1", "C2"): ("coder", "plan"),
    ("C2", "C3"): ("reviewer", "code"),
    ("C3", "C4"): ("reviser", "review_feedback"),
    ("C2", "C4"): ("reviser", "code"),
    ("C4", "C5"): ("executor", "code"),
}

ALLOWED_KINDS = {ArchitectureEditKind.PRUNE_EDGE, ArchitectureEditKind.WEAKEN_EDGE}


def first_prune_or_weaken(
    edits: list[ArchitectureEdit],
    *,
    top1_event: str | None = None,
    target_time_index: dict[str, int] | None = None,
) -> ArchitectureEdit | None:
    """
    Week 6 action-space selection (does not change CR scores).

    1. Only prune_edge / weaken_edge (no verifier).
    2. Skip exogenous C0→* edges.
    3. Prefer edits whose *source* is the CR top-1 event (cut that agent's outputs).
    4. Among those, prefer the consumer closest to the sink (max time_index),
       so e.g. C2→C4 beats C2→C3 for coder faults on the path to execution.
    """
    candidates: list[ArchitectureEdit] = []
    for e in edits:
        if e.kind not in ALLOWED_KINDS or not e.source_event_id or not e.target_event_id:
            continue
        if e.source_event_id == "C0":
            continue
        if not intervention_supported(e):
            continue
        candidates.append(e)
    if not candidates:
        return None

    pool = candidates
    if top1_event:
        outgoing = [e for e in candidates if e.source_event_id == top1_event]
        if outgoing:
            pool = outgoing

    if target_time_index and len(pool) > 1:
        pool = sorted(
            pool,
            key=lambda e: (
                -int(target_time_index.get(e.target_event_id or "", 0)),
                e.kind.value,
                e.target_event_id or "",
            ),
        )
        return pool[0]

    # Preserve CR proposal order among remaining
    return pool[0]


def edit_to_intervention(edit: ArchitectureEdit) -> dict[str, str] | None:
    """Serialize one ArchitectureEdit for AgentState.edge_interventions."""
    if edit.kind not in ALLOWED_KINDS:
        return None
    src, tgt = edit.source_event_id, edit.target_event_id
    if not src or not tgt:
        return None
    if (src, tgt) not in LIVE_EDGE_MAP:
        return None
    return {
        "source_event_id": src,
        "target_event_id": tgt,
        "kind": edit.kind.value,
    }


def intervention_supported(edit: ArchitectureEdit) -> bool:
    return edit_to_intervention(edit) is not None


def _matches(iv: dict[str, Any], src: str, tgt: str) -> bool:
    return iv.get("source_event_id") == src and iv.get("target_event_id") == tgt


def find_intervention(
    interventions: list[dict[str, Any]] | None,
    src: str,
    tgt: str,
) -> dict[str, Any] | None:
    for iv in interventions or []:
        if _matches(iv, src, tgt):
            return iv
    return None


def edge_is_pruned(
    interventions: list[dict[str, Any]] | None, src: str, tgt: str
) -> bool:
    iv = find_intervention(interventions, src, tgt)
    return bool(iv and iv.get("kind") == "prune_edge")


def edge_is_weakened(
    interventions: list[dict[str, Any]] | None, src: str, tgt: str
) -> bool:
    iv = find_intervention(interventions, src, tgt)
    return bool(iv and iv.get("kind") == "weaken_edge")


def gated_parent_text(
    *,
    interventions: list[dict[str, Any]] | None,
    src: str,
    tgt: str,
    factual: str,
    prune_fallback: str,
) -> tuple[str, str | None]:
    """
    Return (effective_payload, gate_mode) for parent src → consumer tgt.

    prune  → prune_fallback (often exogenous task text or empty)
    weaken → channel soft-null
    else   → factual
    """
    iv = find_intervention(interventions, src, tgt)
    if not iv:
        return factual, None
    kind = iv.get("kind")
    if kind == "prune_edge":
        return prune_fallback, "prune_edge"
    if kind == "weaken_edge":
        return _NULL_TEXT, "weaken_edge"
    return factual, None
