"""
Frozen Part III contracts: ArchitectureOperator → ArchitectureProposal.

These interfaces must not leak replay internals. CCAS consumes AttributionReport
only; it must not reach into Exact/Descendant/COW engines.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, Field

from commscm.attribution.report import AttributionReport
from commscm.schema.events import RunTrace


class ArchitectureEditKind(str, Enum):
    """Closed set of architecture edits CCAS may propose (Phase A ranking set)."""

    PRUNE_EDGE = "prune_edge"
    WEAKEN_EDGE = "weaken_edge"
    INSERT_VERIFIER = "insert_verifier"
    REROUTE_CHANNEL = "reroute_channel"
    NO_OP = "no_op"


class ArchitectureEdit(BaseModel):
    """Single atomic architecture modification."""

    kind: ArchitectureEditKind
    # Event / agent endpoints the edit touches (ids from the factual graph).
    source_event_id: str | None = None
    target_event_id: str | None = None
    channel: str | None = None
    # Optional parameters (e.g., verifier policy id). Opaque to Parts I–II.
    params: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class ArchitectureProposal(BaseModel):
    """
    Frozen output of an ArchitectureOperator.

    Rationale may cite CR ranks / event ids from AttributionReport, but must not
    embed replay cost breakdowns or engine-specific fields.
    """

    proposal_id: str
    base_architecture_id: str
    edits: list[ArchitectureEdit] = Field(default_factory=list)
    # Human/algorithm rationale: which attributed events motivated the edits.
    motivating_event_ids: list[str] = Field(default_factory=list)
    expected_utility: float | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class ArchitectureOperator(Protocol):
    """
    Frozen CCAS-facing operator.

    Input: factual trace + attribution report.
    Output: architecture proposal (edits relative to base architecture).
    """

    def propose(
        self,
        trace: RunTrace,
        report: AttributionReport,
    ) -> ArchitectureProposal:
        ...

    def apply(
        self,
        architecture_id: str,
        proposal: ArchitectureProposal,
    ) -> str:
        """Return the id of the resulting architecture after applying edits."""
        ...
