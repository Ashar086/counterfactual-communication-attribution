"""Localization metrics for communication-fault attribution."""

from __future__ import annotations

import math
from typing import Iterable

from pydantic import BaseModel, Field

from commscm.attribution.exact import ExactAttributionReport


class LocalizationMetrics(BaseModel):
    n: int
    precision_at_1: float
    recall_at_k: dict[int, float] = Field(default_factory=dict)
    mrr: float
    mean_replay_ms: float
    mean_recomputed_events: float

    model_config = {"extra": "forbid"}


class MultiFaultMetrics(BaseModel):
    n: int
    recall_at_2: float
    recall_at_k: dict[int, float] = Field(default_factory=dict)
    ndcg_at_2: float
    ndcg_at_k: dict[int, float] = Field(default_factory=dict)
    mean_kendall_tau: float
    mean_spearman: float
    mean_replay_ms: float

    model_config = {"extra": "forbid"}


def _rank_of_gold(report: ExactAttributionReport) -> int | None:
    gold = report.gold_fault_event_id
    if not gold:
        return None
    for row in report.rows:
        if row.event_id == gold:
            return row.rank
    return None


def _gold_ids(report: ExactAttributionReport) -> set[str]:
    # Prefer multi-id list from report extra if present; else single gold.
    extra_ids = report.extra.get("gold_fault_event_ids") if report.extra else None
    if extra_ids:
        return set(extra_ids)
    if report.gold_fault_event_id:
        return {report.gold_fault_event_id}
    return set()


def aggregate_localization(
    reports: list[ExactAttributionReport],
    *,
    ks: tuple[int, ...] = (1, 3, 5),
) -> LocalizationMetrics:
    if not reports:
        raise ValueError("no reports")
    hits1 = 0
    rr_sum = 0.0
    recall_hits = {k: 0 for k in ks}
    replay_ms = 0.0
    recomputed = 0.0
    n_replay = 0

    for r in reports:
        rank = _rank_of_gold(r)
        if rank is None:
            continue
        if rank == 1:
            hits1 += 1
        rr_sum += 1.0 / rank
        for k in ks:
            if rank <= k:
                recall_hits[k] += 1
        for row in r.rows:
            replay_ms += row.runtime_ms
            recomputed += row.recomputed_count
            n_replay += 1

    n = len(reports)
    return LocalizationMetrics(
        n=n,
        precision_at_1=hits1 / n,
        recall_at_k={k: recall_hits[k] / n for k in ks},
        mrr=rr_sum / n,
        mean_replay_ms=(replay_ms / n_replay) if n_replay else 0.0,
        mean_recomputed_events=(recomputed / n_replay) if n_replay else 0.0,
    )


def _dcg(relevances: list[float]) -> float:
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances))


def ndcg_at_k(ranked_ids: list[str], gold: set[str], k: int) -> float:
    rels = [1.0 if eid in gold else 0.0 for eid in ranked_ids[:k]]
    dcg = _dcg(rels)
    ideal = _dcg([1.0] * min(k, len(gold)) + [0.0] * max(0, k - len(gold)))
    return (dcg / ideal) if ideal > 0 else 0.0


def recall_at_k(ranked_ids: list[str], gold: set[str], k: int) -> float:
    if not gold:
        return 0.0
    hit = sum(1 for eid in ranked_ids[:k] if eid in gold)
    return hit / len(gold)


def _rankdata(values: list[float]) -> list[float]:
    """Average ranks for ties (1-based)."""
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for t in range(i, j + 1):
            ranks[order[t]] = avg
        i = j + 1
    return ranks


def spearman_corr(x: list[float], y: list[float]) -> float:
    if len(x) != len(y) or len(x) < 2:
        return 0.0
    rx, ry = _rankdata(x), _rankdata(y)
    n = len(x)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    denx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    deny = math.sqrt(sum((b - my) ** 2 for b in ry))
    if denx == 0 or deny == 0:
        return 0.0
    return num / (denx * deny)


def kendall_tau(x: list[float], y: list[float]) -> float:
    """Tau-a on pairs (no tie adjustment beyond skipping equal-x or equal-y pairs)."""
    n = len(x)
    if n < 2:
        return 0.0
    conc = disc = 0
    for i in range(n):
        for j in range(i + 1, n):
            dx = x[i] - x[j]
            dy = y[i] - y[j]
            if dx == 0 or dy == 0:
                continue
            if dx * dy > 0:
                conc += 1
            else:
                disc += 1
    tot = conc + disc
    return ((conc - disc) / tot) if tot else 0.0


def aggregate_multi_fault(
    reports: list[ExactAttributionReport],
    gold_ids_per_report: list[set[str]],
    *,
    ks: tuple[int, ...] = (2, 3, 5),
) -> MultiFaultMetrics:
    if not reports or len(reports) != len(gold_ids_per_report):
        raise ValueError("reports/gold length mismatch")

    rec = {k: 0.0 for k in ks}
    ndcg = {k: 0.0 for k in ks}
    taus: list[float] = []
    spearmans: list[float] = []
    replay_ms = 0.0
    n_replay = 0

    for report, gold in zip(reports, gold_ids_per_report):
        ranked = [row.event_id for row in report.rows]
        scores = [row.delta_y for row in report.rows]
        relevance = [1.0 if eid in gold else 0.0 for eid in ranked]
        for k in ks:
            rec[k] += recall_at_k(ranked, gold, k)
            ndcg[k] += ndcg_at_k(ranked, gold, k)
        taus.append(kendall_tau(scores, relevance))
        spearmans.append(spearman_corr(scores, relevance))
        for row in report.rows:
            replay_ms += row.runtime_ms
            n_replay += 1

    n = len(reports)
    return MultiFaultMetrics(
        n=n,
        recall_at_2=rec.get(2, 0.0) / n,
        recall_at_k={k: rec[k] / n for k in ks},
        ndcg_at_2=ndcg.get(2, 0.0) / n,
        ndcg_at_k={k: ndcg[k] / n for k in ks},
        mean_kendall_tau=sum(taus) / n,
        mean_spearman=sum(spearmans) / n,
        mean_replay_ms=(replay_ms / n_replay) if n_replay else 0.0,
    )
