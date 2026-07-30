"""
Unified Communication Responsibility (CR) — content-first, typed soft interventions.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CommunicationResponsibility(BaseModel):
    """
    Unified CR for event k (Week-2 exact convention):

        CR(k) = Y_factual - Y_counterfactual
        ΔY(k) = Y_counterfactual - Y_factual   (stored in meta["delta_y"] when used)

    Localization ranks by ΔY descending (nulling the true fault raises Y the most).
    There is no separate CR_e / do(C=∅).
    """

    event_id: str
    channel: str
    factual_reward: float
    counterfactual_reward: float
    cr: float
    meta: dict = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


def cr_from_estimates(
    *,
    event_id: str,
    channel: str,
    factual_reward: float,
    counterfactual_reward: float,
    meta: dict | None = None,
) -> CommunicationResponsibility:
    cr = float(factual_reward) - float(counterfactual_reward)
    payload = dict(meta or {})
    payload.setdefault("delta_y", float(counterfactual_reward) - float(factual_reward))
    return CommunicationResponsibility(
        event_id=event_id,
        channel=channel,
        factual_reward=float(factual_reward),
        counterfactual_reward=float(counterfactual_reward),
        cr=cr,
        meta=payload,
    )


def rank_by_cr(
    scores: list[CommunicationResponsibility],
) -> list[CommunicationResponsibility]:
    """Rank by ΔY descending (improvement when soft-nulled)."""
    return sorted(
        scores,
        key=lambda s: (-float(s.meta.get("delta_y", -s.cr)), s.event_id),
    )
