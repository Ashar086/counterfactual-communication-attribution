import json
from pathlib import Path

ids = [
    "scikit-learn__scikit-learn-14710",
    "scikit-learn__scikit-learn-14894",
    "sympy__sympy-13974",
    "sympy__sympy-14248",
    "sympy__sympy-15976",
    "sympy__sympy-17655",
]
root = Path(
    "logs/run_evaluation/vi_b_rescore_part_vi_b_official_cr_guided/commscm-vi-b-cr_guided"
)
agg = Path("results/commscm-vi-b-cr_guided.vi_b_rescore_part_vi_b_official_cr_guided.json")
if agg.exists():
    r = json.loads(agg.read_text(encoding="utf-8"))
    print("AGGREGATE (resume batch)")
    print("  resolved_ids:", r.get("resolved_ids"))
    print("  unresolved_ids:", r.get("unresolved_ids"))
    print("  error_ids:", r.get("error_ids"))
    print()

print("PER INSTANCE")
for iid in ids:
    d = root / iid
    rj = d / "report.json"
    log = d / "run_instance.log"
    if rj.exists():
        data = json.loads(rj.read_text(encoding="utf-8")).get(iid, {})
        print(f"{iid}: unresolved/applied report resolved={data.get('resolved')} applied={data.get('patch_successfully_applied')}")
    elif log.exists() and log.stat().st_size:
        t = log.read_text(encoding="utf-8", errors="replace")
        if "Patch Apply Failed" in t:
            print(f"{iid}: ERROR patch-apply-failed")
        elif "pulling image" in t and "Error" in t:
            print(f"{iid}: ERROR pull-failed")
        else:
            print(f"{iid}: ERROR/other (log {log.stat().st_size} bytes)")
    else:
        print(f"{iid}: MISSING")
