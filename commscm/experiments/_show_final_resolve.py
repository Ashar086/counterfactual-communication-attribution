import json
from pathlib import Path
from collections import Counter, defaultdict

for m in ["cr_guided", "reward_only", "random", "static_heuristic"]:
    p = Path(f"results/commscm-vi-b-{m}.vi_b_rescore_part_vi_b_official_{m}.json")
    if not p.exists():
        print(m, "NO_REPORT")
        continue
    r = json.loads(p.read_text(encoding="utf-8"))
    print(
        f"{m}: resolved={len(r.get('resolved_ids') or [])} "
        f"unresolved={len(r.get('unresolved_ids') or [])} "
        f"errors={len(r.get('error_ids') or [])}"
    )

cp = json.loads(Path("results/part_vi_b_official.json").read_text(encoding="utf-8"))
print("docker_rescored", cp.get("docker_rescored"), "resume", cp.get("docker_resume"))
by = defaultdict(Counter)
for r in cp.get("rows") or []:
    by[r["method"]][str(r.get("resolve_at_1"))] += 1
for m, c in by.items():
    print("checkpoint", m, dict(c))
