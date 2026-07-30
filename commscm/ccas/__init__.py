"""CCAS package — Part III architecture optimization."""

from commscm.ccas.apply_edit import ArchitectureRegistry, apply_edit_to_trace, apply_single_edit
from commscm.ccas.interfaces import (
    ArchitectureEdit,
    ArchitectureEditKind,
    ArchitectureOperator,
    ArchitectureProposal,
)
from commscm.ccas.loop import CCASLoop, CCASResult
from commscm.ccas.operators import CRGuidedOperator, RandomOperator, RewardOnlyOperator

__all__ = [
    "ArchitectureEdit",
    "ArchitectureEditKind",
    "ArchitectureOperator",
    "ArchitectureProposal",
    "ArchitectureRegistry",
    "CCASLoop",
    "CCASResult",
    "CRGuidedOperator",
    "RandomOperator",
    "RewardOnlyOperator",
    "apply_edit_to_trace",
    "apply_single_edit",
]

