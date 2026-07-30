"""
CommSCM v0.1 — Frozen research identity.

One-sentence contribution
-------------------------
Counterfactual Communication Attribution: A causal framework that attributes
failures to typed information-flow events and uses those attributions to
optimize multi-agent communication architectures.

Supporting machinery (not co-equal headlines)
---------------------------------------------
- IF-C-SCM          formalism (time-indexed event DAG)
- CR                unified Communication Responsibility via typed soft interventions
- CCAS              optimization algorithm driven by CR
- CausalCommBench   controlled evaluation (+ SWE / WebArena / AgentDojo later)

Discipline
----------
No new definitions unless an experiment forces them.
Literal do(C=∅) is NOT a primary object. Use null-input soft interventions.
"""

from commscm.attribution.responsibility import (
    CommunicationResponsibility,
    cr_from_estimates,
    rank_by_cr,
)
from commscm.interventions.soft import (
    NullTemplates,
    SoftIntervention,
    apply_soft_intervention,
)
from commscm.schema.events import Channel, CommunicationEvent, EventDAG, RunTrace

__all__ = [
    "Channel",
    "CommunicationEvent",
    "CommunicationResponsibility",
    "EventDAG",
    "NullTemplates",
    "RunTrace",
    "SoftIntervention",
    "apply_soft_intervention",
    "cr_from_estimates",
    "rank_by_cr",
]

__version__ = "0.1.0"
