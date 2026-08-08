"""Ad-hoc partial VI.B analysis (finished rows only). Does not touch the running job."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

rows = json.loads(Path("results/part_vi_b_official.json").read_text(encoding="utf-8"))["rows"]

print("=== CHECKPOINT ===")
print(f"n_rows={len(rows)}/400 partial=True")
print(f"pipeline_ok={sum(1 for r in rows if r.get('pipeline_ok'))}")
print(f"with_patch={sum(1 for r in rows if (r.get('model_patch') or '').strip())}")
print(f"resolve_field_set={sum(1 for r in rows if r.get('resolve_at_1') is not None)}")

print("\n=== PROXY / ATTRIBUTION (finished LLM rows) ===")
for m in ["cr_guided", "reward_only", "random", "static_heuristic"]:
    mrows = [r for r in rows if r.get("method") == m]
    n = len(mrows)
    if not n:
        continue
    geh = sum(1 for r in mrows if r.get("hit_gold_edge")) / n
    p1 = sum(float(r.get("p_at_1") or 0) for r in mrows) / n
    proxy_pass = sum(1 for r in mrows if (r.get("y_proxy_after") or 0) >= 1.0) / n
    fails = Counter(r.get("failure_code") for r in mrows)
    print(
        f"{m}: n={n} CR_P@1={p1:.2f} gold_edge={geh:.2f} "
        f"proxy_pass={proxy_pass:.2f} fails={dict(fails)}"
    )

print("\n=== HARNESS REPORTS (Resolve@1 where Docker finished) ===")
resolve_by: dict[tuple[str, str], float | None] = {}
reports = sorted(Path(".").glob("commscm-vi-b-*.vi_b_part_vi_b_official_*.json"))
print(f"n_reports={len(reports)}")
for rp in reports:
    method = rp.name.split(".")[0].replace("commscm-vi-b-", "")
    rep = json.loads(rp.read_text(encoding="utf-8"))
    for iid in rep.get("resolved_ids") or []:
        resolve_by[(method, str(iid))] = 1.0
    for iid in rep.get("unresolved_ids") or []:
        resolve_by.setdefault((method, str(iid)), 0.0)
    for iid in rep.get("error_ids") or []:
        resolve_by[(method, str(iid))] = None
    print(
        f"  {rp.name}: resolved={rep.get('resolved_instances')} "
        f"unresolved={rep.get('unresolved_instances')} "
        f"errors={rep.get('error_instances')}"
    )

print(f"\nn_resolve_keys={len(resolve_by)}")
by_m: dict[str, list] = defaultdict(list)
for (method, iid), val in resolve_by.items():
    by_m[method].append(val)

for m in ["cr_guided", "reward_only", "random", "static_heuristic"]:
    xs = by_m.get(m, [])
    scored = [x for x in xs if x is not None]
    errs = sum(1 for x in xs if x is None)
    mean = sum(scored) / len(scored) if scored else None
    print(f"{m}: docker_n={len(xs)} scored={len(scored)} errors={errs} resolve_mean={mean}")

# Note on batch jsonl diversity
p = Path("results/part_vi_b_predictions/vi_b_part_vi_b_official_1.jsonl")
if p.exists():
    models = []
    for line in p.read_text(encoding="utf-8").splitlines():
        o = json.loads(line)
        models.append(o["model_name_or_path"])
    print("\nbatch1 model_name_or_path values:", models)
    print(
        "NOTE: harness appears to evaluate one model_name per run_id; "
        "batches with 4 methods may only score 1 method's patch."
    )

print("\n=== VERDICT ON PARTIAL ===")
print("LLM/attribution partial looks HEALTHY and directionally consistent with shaped pilot.")
print("Official Resolve@1 not yet usable for method comparison (merge gap + single-model-per-batch).")
print("Do NOT update CLAIMS_LEDGER or decision path until full run + fixed resolve join.")
