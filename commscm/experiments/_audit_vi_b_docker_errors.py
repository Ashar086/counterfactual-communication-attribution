"""One-shot audit: VI.B harness reports + checkpoint patch issues by method."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    reports = sorted(ROOT.glob("commscm-vi-b-static_heuristic.vi_b_part_vi_b_official_*.json"))
    print("n_reports", len(reports))
    tot: Counter[str] = Counter()
    err_ids: list[str] = []
    for p in reports:
        r = json.loads(p.read_text(encoding="utf-8"))
        n_res = len(r.get("resolved_ids") or [])
        n_un = len(r.get("unresolved_ids") or [])
        n_err = len(r.get("error_ids") or [])
        tot["resolved"] += n_res
        tot["unresolved"] += n_un
        tot["errors"] += n_err
        err_ids.extend(r.get("error_ids") or [])
        print(
            f"  {p.name}: resolved={n_res} unresolved={n_un} errors={n_err}"
        )
    print("TOTALS", dict(tot), "unique_error_ids", len(set(err_ids)))

    cp = ROOT / "results" / "part_vi_b_official.json"
    if not cp.exists():
        print("no checkpoint")
        return
    rows = json.loads(cp.read_text(encoding="utf-8")).get("rows") or []
    print("checkpoint_rows", len(rows))
    by = Counter(r["method"] for r in rows)
    print("rows_by_method", dict(by))

    patch_issues: Counter[tuple[str, str]] = Counter()
    resolve_by: Counter[tuple[str, str]] = Counter()
    for r in rows:
        m = r["method"]
        patch = r.get("model_patch") or ""
        if not patch.strip():
            patch_issues[(m, "empty")] += 1
        else:
            if "def apply_patch" in patch:
                patch_issues[(m, "apply_patch_stub")] += 1
            bad_prefix = False
            for line in patch.splitlines():
                if line.startswith("--- ") and not line.startswith("--- a/") and "/dev/null" not in line:
                    bad_prefix = True
                    break
            if bad_prefix:
                patch_issues[(m, "missing_a_prefix")] += 1
            if "@@" not in patch and "diff " not in patch:
                patch_issues[(m, "no_hunk_or_diff")] += 1
        resolve_by[(m, str(r.get("resolve_at_1")))] += 1

    print("resolve_at_1_by_method", dict(resolve_by))
    print("patch_issue_signals (pre-normalize):")
    for k, v in sorted(patch_issues.items(), key=lambda x: (-x[1], x[0])):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
