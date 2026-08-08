"""
Part VI.B frozen analysis (Result-Blind): bootstrap CIs + effect sizes.

Do not change statistical choices after opening results.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

METHODS = ("cr_guided", "reward_only", "random", "static_heuristic")


def _bootstrap_mean_ci(xs: list[float], *, B: int = 10_000, alpha: float = 0.05, seed: int = 0):
    if not xs:
        return None, (None, None)
    rng = random.Random(seed)
    n = len(xs)
    means = []
    for _ in range(B):
        sample = [xs[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int((alpha / 2) * B)]
    hi = means[int((1 - alpha / 2) * B) - 1]
    return sum(xs) / n, (lo, hi)


def _cohens_dz(diffs: list[float]) -> float | None:
    if len(diffs) < 2:
        return None
    m = sum(diffs) / len(diffs)
    var = sum((d - m) ** 2 for d in diffs) / (len(diffs) - 1)
    sd = var**0.5
    if sd == 0:
        return 0.0
    return m / sd


def analyze(rows: list[dict]) -> dict:
    by_m: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("method") in METHODS:
            by_m[r["method"]].append(r)

    summary: dict = {"by_method": {}, "contrasts": {}, "process": {}}
    for m in METHODS:
        mrows = by_m[m]
        resolve = [float(r["resolve_at_1"]) for r in mrows if r.get("resolve_at_1") is not None]
        p_at_1 = [float(r["p_at_1"]) for r in mrows if r.get("p_at_1") is not None]
        geh = [1.0 if r.get("hit_gold_edge") else 0.0 for r in mrows if "hit_gold_edge" in r]
        repaired = [
            r
            for r in mrows
            if r.get("hit_gold_edge") and r.get("resolve_at_1") is not None
        ]
        rap_num = sum(1 for r in repaired if r.get("hit_gold_edge"))
        # RAP among rows that resolved after CR-guided gold hit is approximate;
        # prereg: RAP = edit targets attributed harmful communication among repairs.
        gold_edits = [r for r in mrows if r.get("n_edits")]
        rap = (
            sum(1 for r in gold_edits if r.get("hit_gold_edge")) / len(gold_edits)
            if gold_edits
            else None
        )
        mean_r, ci_r = _bootstrap_mean_ci(resolve, seed=hash(m) % 10_000)
        mean_p, ci_p = _bootstrap_mean_ci(p_at_1, seed=hash(m + "p") % 10_000)
        mean_g, ci_g = _bootstrap_mean_ci(geh, seed=hash(m + "g") % 10_000)
        summary["by_method"][m] = {
            "n": len(mrows),
            "n_resolve_scored": len(resolve),
            "resolve_at_1_mean": mean_r,
            "resolve_at_1_ci95": ci_r,
            "p_at_1_mean": mean_p,
            "p_at_1_ci95": ci_p,
            "gold_edge_hit_mean": mean_g,
            "gold_edge_hit_ci95": ci_g,
            "rap": rap,
            "pipeline_ok_rate": (
                sum(1 for r in mrows if r.get("pipeline_ok")) / len(mrows) if mrows else 0.0
            ),
        }

    # Paired CR vs reward-only on shared instance_ids with both resolve scores
    cr = {r["instance_id"]: r for r in by_m["cr_guided"] if r.get("resolve_at_1") is not None}
    ro = {r["instance_id"]: r for r in by_m["reward_only"] if r.get("resolve_at_1") is not None}
    shared = sorted(set(cr) & set(ro))
    diffs = [float(cr[i]["resolve_at_1"]) - float(ro[i]["resolve_at_1"]) for i in shared]
    mean_d, ci_d = _bootstrap_mean_ci(diffs, seed=123) if diffs else (None, (None, None))
    summary["contrasts"]["cr_minus_reward_only_resolve"] = {
        "n_paired": len(shared),
        "mean_diff": mean_d,
        "ci95": ci_d,
        "cohens_dz": _cohens_dz(diffs) if diffs else None,
    }

    n = len(rows)
    ok = sum(1 for r in rows if r.get("pipeline_ok") and r.get("repair_pipeline_ok"))
    summary["process"] = {
        "n_rows": n,
        "pipeline_success_rate": ok / n if n else 0.0,
        "p1_ge_95": (ok / n >= 0.95) if n else False,
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="inp", default="results/part_vi_b_official.json")
    parser.add_argument("--out", default="results/part_vi_b_analysis.json")
    args = parser.parse_args()
    payload = json.loads(Path(args.inp).read_text(encoding="utf-8"))
    summary = analyze(list(payload.get("rows") or []))
    out = {
        "experiment": "part_vi_b_analyze",
        "source": args.inp,
        "stats": {
            "bootstrap_B": 10_000,
            "ci": "95%",
            "primary_contrast": "cr_guided vs reward_only Resolve@1",
        },
        "summary": summary,
    }
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
