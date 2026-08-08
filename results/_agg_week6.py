import json
from collections import Counter
from pathlib import Path

from commscm.experiments.week6_live_repair import aggregate

p = Path("results/week6_live_repair.json")
d = json.loads(p.read_text(encoding="utf-8"))
rows = d["rows"]
print(
    "method x mode",
    Counter((r["method"], r["poison_mode"]) for r in rows if not r.get("skipped")),
)
summary = aggregate(rows)
d["summary"] = summary
d["partial"] = False
p.write_text(json.dumps(d, indent=2), encoding="utf-8")
print("gate", summary["week6_gate_pass"])
print("mean_edit_stability", summary["mean_edit_stability"])
print()
for m in ["random", "reward_only", "cr_guided"]:
    b = summary["by_method"][m]
    print(
        f"{m}: n={b['n']} repair={b['frac_repaired']:.3f} "
        f"gold={b['gold_edge_hit_rate']:.3f} rap={b['repair_attribution_precision']} "
        f"dY={b['mean_delta_y']:.3f} dLat={b['mean_latency_delta_ms']} "
        f"fails={b['failure_taxonomy']}"
    )
fc: Counter[str] = Counter()
for r in rows:
    if r.get("failure_code"):
        fc[r["failure_code"]] += 1
print("all fails", dict(fc))
print("n_rows", len(rows), "skipped", summary["n_skipped_success"])

# per-mode CR
for mode in ["POISON_PLANNER", "POISON_CODER", "POISON_REVIEWER"]:
    sub = [r for r in rows if r.get("method") == "cr_guided" and r.get("poison_mode") == mode and not r.get("skipped")]
    if not sub:
        continue
    rep = sum(1 for r in sub if r.get("repaired")) / len(sub)
    gold = sum(1 for r in sub if r.get("hit_gold_edge")) / len(sub)
    print(f"CR {mode}: n={len(sub)} repair={rep:.3f} gold={gold:.3f}")
