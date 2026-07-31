"""
Attribution ranking stability metrics (Week 5 appendix / pre-Week-6).

For K independent executions of the same task:
  - top-1 agreement (vs modal top-1; pairwise)
  - mean pairwise Kendall τ on CR rankings (best-first event id lists)
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations


def kendall_tau(order_a: list[str], order_b: list[str]) -> float:
    """
    Kendall τ-a on two total rankings (best-first lists over the same items).

    Returns 1.0 if fewer than 2 items or no comparable pairs.
    """
    set_a, set_b = set(order_a), set(order_b)
    if set_a != set_b:
        # Align on intersection; drop extras (rare under fixed DAG shape)
        common = set_a & set_b
        order_a = [x for x in order_a if x in common]
        order_b = [x for x in order_b if x in common]
    n = len(order_a)
    if n < 2:
        return 1.0
    pos_a = {x: i for i, x in enumerate(order_a)}
    pos_b = {x: i for i, x in enumerate(order_b)}
    items = list(pos_a.keys())
    conc = disc = 0
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            x, y = items[i], items[j]
            sa = pos_a[x] - pos_a[y]
            sb = pos_b[x] - pos_b[y]
            if sa == 0 or sb == 0:
                continue
            if sa * sb > 0:
                conc += 1
            else:
                disc += 1
    denom = conc + disc
    return (conc - disc) / denom if denom else 1.0


def top1_modal_agreement(top1s: list[str | None]) -> dict:
    """Fraction of runs matching the modal top-1 (among non-None)."""
    vals = [t for t in top1s if t is not None]
    if not vals:
        return {"modal_top1": None, "agreement": None, "n": 0}
    modal, _ = Counter(vals).most_common(1)[0]
    agree = sum(1 for t in vals if t == modal) / len(vals)
    return {"modal_top1": modal, "agreement": agree, "n": len(vals)}


def top1_pairwise_agreement(top1s: list[str | None]) -> float | None:
    vals = [t for t in top1s if t is not None]
    pairs = list(combinations(vals, 2))
    if not pairs:
        return None
    return sum(1 for a, b in pairs if a == b) / len(pairs)


def mean_pairwise_kendall(rankings: list[list[str]]) -> float | None:
    clean = [r for r in rankings if len(r) >= 2]
    pairs = list(combinations(clean, 2))
    if not pairs:
        return None
    return sum(kendall_tau(a, b) for a, b in pairs) / len(pairs)


def summarize_stability_group(
    *,
    task_id: str,
    poison_mode: str,
    rows: list[dict],
) -> dict:
    """
    rows: attribution_ok runs with cr_top1 and cr_ranking (best-first list).
    """
    ok = [r for r in rows if r.get("attribution_ok")]
    top1s = [r.get("cr_top1") for r in ok]
    rankings = [list(r.get("cr_ranking") or []) for r in ok]
    modal = top1_modal_agreement(top1s)
    return {
        "task_id": task_id,
        "poison_mode": poison_mode,
        "n_ok": len(ok),
        "n_attempted": len(rows),
        "modal_top1": modal["modal_top1"],
        "top1_agreement_vs_mode": modal["agreement"],
        "top1_pairwise_agreement": top1_pairwise_agreement(top1s),
        "mean_pairwise_kendall_tau": mean_pairwise_kendall(rankings),
        "top1s": top1s,
    }
