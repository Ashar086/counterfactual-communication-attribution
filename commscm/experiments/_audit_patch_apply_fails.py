"""Read-only diagnostic: categorize VI.B patch-apply failures (does not touch running Docker)."""
from __future__ import annotations

import json
import random
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG_ROOT = (
    ROOT
    / "logs/run_evaluation/vi_b_rescore_part_vi_b_official_cr_guided/commscm-vi-b-cr_guided"
)
OUT = ROOT / "results" / "part_vi_b_patch_apply_audit.json"


def categorize(logtext: str, patch: str) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if "malformed patch" in logtext:
        reasons.append("invalid_unified_diff_syntax")
    if "can't find file to patch" in logtext or "No such file or directory" in logtext:
        reasons.append("wrong_file_path")
    if re.search(r"Hunk #\d+ FAILED", logtext) or (
        "hunk FAILED" in logtext.lower()
    ):
        reasons.append("wrong_context_hunk_mismatch")
    if "Reversed (or previously applied)" in logtext:
        reasons.append("stale_or_already_applied")
    if "while deleting" in logtext.lower() or "already deleted" in logtext.lower():
        reasons.append("targets_deleted_lines")

    if patch:
        if "def apply_patch" in patch:
            reasons.append("invalid_unified_diff_syntax")
        if "@@" not in patch:
            reasons.append("invalid_unified_diff_syntax")
        for line in patch.splitlines():
            if line.startswith("--- ") and not line.startswith("--- a/") and "/dev/null" not in line:
                reasons.append("invalid_unified_diff_syntax")
                break
            if line.startswith("+++ ") and not line.startswith("+++ b/") and "/dev/null" not in line:
                reasons.append("invalid_unified_diff_syntax")
                break

    if not reasons:
        reasons.append("other")

    order = [
        "wrong_file_path",
        "wrong_context_hunk_mismatch",
        "invalid_unified_diff_syntax",
        "targets_deleted_lines",
        "stale_or_already_applied",
        "other",
    ]
    primary = "other"
    for o in order:
        if o in reasons:
            primary = o
            break
    return primary, sorted(set(reasons))


def main() -> None:
    cp = json.loads((ROOT / "results" / "part_vi_b_official.json").read_text(encoding="utf-8"))
    rows = {(r["instance_id"], r["method"]): r for r in (cp.get("rows") or [])}

    fails: list[tuple[str, str]] = []
    for log in LOG_ROOT.glob("*/run_instance.log"):
        if log.stat().st_size == 0:
            continue
        t = log.read_text(encoding="utf-8", errors="replace")
        if "Patch Apply Failed" not in t and "malformed patch" not in t:
            continue
        fails.append((log.parent.name, t))

    random.seed(42)
    sample = fails if len(fails) <= 20 else random.sample(fails, 20)

    cats: Counter[str] = Counter()
    details = []
    for inst, t in sample:
        row = rows.get((inst, "cr_guided")) or {}
        patch = row.get("model_patch") or ""
        primary, reasons = categorize(t, patch)
        cats[primary] += 1
        idx = t.find("Patch Apply Failed")
        snippet = (t[idx : idx + 400] if idx >= 0 else t[-350:]).replace("\n", " | ")
        details.append(
            {
                "instance_id": inst,
                "primary": primary,
                "reasons": reasons,
                "hit_gold_edge": row.get("hit_gold_edge"),
                "y_proxy_after": row.get("y_proxy_after"),
                "failure_code": row.get("failure_code"),
                "patch_len": len(patch),
                "patch_has_hunk": "@@" in patch,
                "patch_has_stub": "def apply_patch" in patch,
                "snippet": snippet[:300],
            }
        )

    gold = sum(1 for d in details if d["hit_gold_edge"])
    proxy = sum(1 for d in details if (d["y_proxy_after"] or 0) >= 0.5)

    report = {
        "n_patch_apply_fail_logs": len(fails),
        "n_sampled": len(sample),
        "category_counts": dict(cats),
        "among_sample_hit_gold_edge": gold,
        "among_sample_proxy_pass": proxy,
        "case_hint": (
            "If gold_edge high + proxy high but patch apply fails → Case B/C "
            "(attribution OK-ish; patch emission/adapter weak). "
            "If gold_edge low → Case A more plausible."
        ),
        "details": details,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"n_fail_logs={len(fails)} sampled={len(sample)}")
    print("CATEGORY_COUNTS")
    label = {
        "wrong_file_path": "Wrong file path",
        "wrong_context_hunk_mismatch": "Wrong context / hunk mismatch",
        "invalid_unified_diff_syntax": "Invalid unified diff syntax",
        "targets_deleted_lines": "Patch targets deleted lines",
        "stale_or_already_applied": "Correct syntax but stale repository",
        "other": "Other",
    }
    for k, v in cats.most_common():
        print(f"  {label.get(k, k)}: {v}")
    print(f"hit_gold_edge={gold}/{len(details)} proxy_pass={proxy}/{len(details)}")
    print(f"wrote {OUT}")
    for d in details:
        print(
            f"{d['instance_id']} | {d['primary']} | gold={d['hit_gold_edge']} "
            f"proxy={d['y_proxy_after']} stub={d['patch_has_stub']}"
        )


if __name__ == "__main__":
    main()
