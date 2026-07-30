"""H1 metrics: harmful-edge localization from ranked ArchitectureProposals."""

from __future__ import annotations

import math
from typing import Iterable

from pydantic import BaseModel, Field

from commscm.ccas.interfaces import ArchitectureProposal
from commscm.ccas.operators import unique_edges_in_order


class H1EdgeMetrics(BaseModel):
    n: int
    precision_at_1: float
    recall_at_k: dict[int, float] = Field(default_factory=dict)
    ndcg_at_k: dict[int, float] = Field(default_factory=dict)
    false_positive_edit_rate: float

    model_config = {"extra": "forbid"}


def _dcg(relevances: list[float]) -> float:
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances))


def score_proposal(
    proposal: ArchitectureProposal,
    gold: set[tuple[str, str]],
    *,
    ks: tuple[int, ...] = (1, 3, 5),
) -> dict:
    ranked = unique_edges_in_order(proposal.edits)
    if not ranked:
        return {
            "hit_at_1": False,
            "fp_at_1": True,
            "recall_at_k": {k: 0.0 for k in ks},
            "ndcg_at_k": {k: 0.0 for k in ks},
        }
    top1 = ranked[0]
    hit1 = top1 in gold
    recalls = {}
    ndcgs = {}
    for k in ks:
        topk = ranked[:k]
        if gold:
            recalls[k] = len(set(topk) & gold) / len(gold)
        else:
            recalls[k] = 0.0
        rels = [1.0 if e in gold else 0.0 for e in topk]
        ideal = sorted([1.0] * min(len(gold), k) + [0.0] * max(0, k - len(gold)), reverse=True)[:k]
        idcg = _dcg(ideal)
        ndcgs[k] = (_dcg(rels) / idcg) if idcg > 0 else 0.0
    return {
        "hit_at_1": hit1,
        "fp_at_1": not hit1,
        "recall_at_k": recalls,
        "ndcg_at_k": ndcgs,
    }


def aggregate_h1(
    results: Iterable[dict],
    *,
    ks: tuple[int, ...] = (1, 3, 5),
) -> H1EdgeMetrics:
    rows = list(results)
    if not rows:
        raise ValueError("no H1 results")
    n = len(rows)
    p1 = sum(1 for r in rows if r["hit_at_1"]) / n
    fp = sum(1 for r in rows if r["fp_at_1"]) / n
    recall = {k: sum(r["recall_at_k"][k] for r in rows) / n for k in ks}
    ndcg = {k: sum(r["ndcg_at_k"][k] for r in rows) / n for k in ks}
    return H1EdgeMetrics(
        n=n,
        precision_at_1=p1,
        recall_at_k=recall,
        ndcg_at_k=ndcg,
        false_positive_edit_rate=fp,
    )
