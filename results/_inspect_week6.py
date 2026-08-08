import json
from collections import Counter
from pathlib import Path

d = json.loads(Path("results/week6_live_repair.json").read_text(encoding="utf-8"))
for mode in ["POISON_PLANNER", "POISON_CODER", "POISON_REVIEWER"]:
    print("===", mode, "===")
    for r in d["rows"]:
        if r.get("method") != "cr_guided" or r.get("poison_mode") != mode:
            continue
        print(
            r["task_id"],
            "edit=",
            r.get("edit_key"),
            "gold=",
            r.get("hit_gold_edge"),
            "y",
            r.get("y_before"),
            "->",
            r.get("y_after"),
            "fail=",
            r.get("failure_code"),
            "cr_top1=",
            r.get("cr_top1"),
        )
    print()
