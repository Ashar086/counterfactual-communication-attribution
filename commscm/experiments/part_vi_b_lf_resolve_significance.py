"""VI.B LF Resolve@1 significance + CIs (no CommSCM changes)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.stats import chi2_contingency, fisher_exact
from statsmodels.stats.proportion import proportion_confint

OUT_DIR = Path("results")
METHODS = [
    ("cr_guided", "CR-guided", 2),
    ("reward_only", "Reward-only", 4),
    ("random", "Random", 3),
    ("static_heuristic", "Static", 3),
]
N = 100
ALPHA = 0.05
RNG = np.random.default_rng(42)
MC_REPS = 200_000


def wilson_ci(k: int, n: int, alpha: float = ALPHA) -> tuple[float, float]:
    lo, hi = proportion_confint(k, n, alpha=alpha, method="wilson")
    return float(lo), float(hi)


def clopper_pearson_ci(k: int, n: int, alpha: float = ALPHA) -> tuple[float, float]:
    lo, hi = proportion_confint(k, n, alpha=alpha, method="beta")
    return float(lo), float(hi)


def fisher_2x2(k1: int, n1: int, k2: int, n2: int) -> dict:
    table = np.array([[k1, n1 - k1], [k2, n2 - k2]], dtype=int)
    odds, p = fisher_exact(table, alternative="two-sided")
    return {
        "table": table.tolist(),
        "odds_ratio": float(odds) if np.isfinite(odds) else None,
        "p_value": float(p),
        "test": "Fisher exact (two-sided)",
    }


def freeman_halton_mc(successes: list[int], n: int, reps: int = MC_REPS) -> dict:
    """Monte Carlo estimate of exact-style multiway test under fixed margins.

    For equal row totals n and column totals [S, G*n-S], sample resolved counts
    by drawing S labeled trials without replacement from G groups of size n
    (multivariate hypergeometric), and compare Pearson chi-square to observed.
    """
    succ = np.asarray(successes, dtype=int)
    g = len(succ)
    S = int(succ.sum())
    table_obs = np.vstack([succ, n - succ]).T
    chi_obs, p_chi, dof, expected = chi2_contingency(table_obs)

    colors = np.repeat(np.arange(g), n)
    count_ge = 0
    for _ in range(reps):
        drawn = RNG.choice(colors, size=S, replace=False)
        sim = np.bincount(drawn, minlength=g)
        table_sim = np.vstack([sim, n - sim]).T
        chi_sim, *_ = chi2_contingency(table_sim, correction=False)
        if chi_sim >= chi_obs - 1e-12:
            count_ge += 1
    p_mc = (count_ge + 1) / (reps + 1)
    return {
        "test": "Freeman-Halton-style Monte Carlo (fixed margins; chi2 ranking)",
        "statistic_chi2_obs": float(chi_obs),
        "df": int(dof),
        "expected": expected.tolist(),
        "p_value_chi2_asymptotic": float(p_chi),
        "p_value_monte_carlo": float(p_mc),
        "monte_carlo_reps": reps,
        "note": (
            "Asymptotic chi-square may be unreliable: several expected cell counts < 5. "
            "Prefer Monte Carlo p-value for the overall test."
        ),
    }


def main() -> None:
    rows = []
    for key, label, k in METHODS:
        rate = k / N
        w_lo, w_hi = wilson_ci(k, N)
        cp_lo, cp_hi = clopper_pearson_ci(k, N)
        rows.append(
            {
                "method_key": key,
                "method": label,
                "resolved": k,
                "n": N,
                "rate": rate,
                "wilson_95ci": [w_lo, w_hi],
                "clopper_pearson_95ci": [cp_lo, cp_hi],
            }
        )

    cr_k = 2
    pairwise = {}
    for key, label, k in METHODS[1:]:
        pairwise[key] = {
            "comparison": f"CR-guided vs {label}",
            **fisher_2x2(cr_k, N, k, N),
        }

    overall = freeman_halton_mc([k for _, _, k in METHODS], N)

    paper_lines = [
        "Table. VI.B LF-rescored Resolve@1 with 95% Wilson CIs and pairwise Fisher exact tests vs CR-guided (n=100).",
        "",
        "| Method | Resolved/n | Rate | 95% Wilson CI | p vs CR-guided (Fisher exact) |",
        "|---|---:|---:|---|---:|",
    ]
    for r in rows:
        key = r["method_key"]
        lo, hi = r["wilson_95ci"]
        if key == "cr_guided":
            p_str = "—"
        else:
            p_str = f"{pairwise[key]['p_value']:.4g}"
        paper_lines.append(
            f"| {r['method']} | {r['resolved']}/{r['n']} | {r['rate']:.2f} | "
            f"[{lo:.3f}, {hi:.3f}] | {p_str} |"
        )
    paper_lines += [
        "",
        f"Overall (4x2) asymptotic chi-square p = {overall['p_value_chi2_asymptotic']:.4g} "
        f"(df={overall['df']}); Monte Carlo exact-style p = {overall['p_value_monte_carlo']:.4g} "
        f"({overall['monte_carlo_reps']:,} reps). Prefer MC given sparse cells.",
        "",
        "Clopper-Pearson 95% CIs (supplement):",
    ]
    for r in rows:
        lo, hi = r["clopper_pearson_95ci"]
        paper_lines.append(f"- {r['method']}: [{lo:.3f}, {hi:.3f}]")

    payload = {
        "experiment": "part_vi_b_lf_resolve_significance",
        "source": "results/part_vi_b_lf_rescore_summary.json / overnight_lf_campaign_final.json",
        "n": N,
        "selection_seed": 42,
        "outcome": "Resolve@1 (resolved vs not-resolved; errors+unresolved counted as not resolved)",
        "methods": rows,
        "pairwise_vs_cr_guided": pairwise,
        "overall_4x2": overall,
        "decision_rule": (
            "Fisher exact preferred for pairwise 2x2 with expected counts < 5; "
            "Wilson CI primary for rates; Clopper-Pearson reported as sensitivity."
        ),
        "paper_table_md": "\n".join(paper_lines),
    }

    out_json = OUT_DIR / "part_vi_b_lf_resolve_significance.json"
    out_md = OUT_DIR / "part_vi_b_lf_resolve_significance.md"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    out_md.write_text(
        "# VI.B LF Resolve@1 — significance & CIs\n\n"
        + payload["paper_table_md"]
        + "\n\n## Pairwise Fisher exact detail\n\n"
        + "\n".join(
            f"- **{v['comparison']}**: OR={v['odds_ratio']}, p={v['p_value']:.6g}, table={v['table']}"
            for v in pairwise.values()
        )
        + "\n\n## Overall test\n\n"
        + f"- chi-square (asymptotic) = {overall['statistic_chi2_obs']:.4f}, df={overall['df']}, "
        + f"p={overall['p_value_chi2_asymptotic']:.6g}\n"
        + f"- Monte Carlo p = {overall['p_value_monte_carlo']:.6g} "
        + f"(reps={overall['monte_carlo_reps']})\n"
        + f"- Note: {overall['note']}\n",
        encoding="utf-8",
    )

    # Avoid Windows console UnicodeEncodeError
    print(payload["paper_table_md"].encode("ascii", "replace").decode("ascii"))
    print()
    print("Wrote", out_json, "and", out_md)
    for k, v in pairwise.items():
        print(f"pairwise {k}: p={v['p_value']:.6g}")
    print(
        f"overall chi2 p={overall['p_value_chi2_asymptotic']:.6g} "
        f"mc p={overall['p_value_monte_carlo']:.6g}"
    )


if __name__ == "__main__":
    main()
