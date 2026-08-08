"""
Rescore CR-guided VI.B synthesized patches on a sample with LF-fixed harness.

Uses the same instance IDs as the oracle gold sample (seed=7, n=10) for
comparability. Does not re-run LLMs or touch CommSCM core.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from commscm.adapters.swebench.official_eval import (
    load_harness_report,
    run_official_evaluation,
    write_predictions_jsonl,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--official", default="results/part_vi_b_official.json")
    ap.add_argument("--gold-sample", default="results/oracle_gold_patch_sample.json")
    ap.add_argument("--run-id", default="cr_guided_sample_n10_s7_lf")
    ap.add_argument("--max-workers", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--out", default="results/cr_guided_sample_n10_s7_lf.json")
    args = ap.parse_args()

    gold = json.loads(Path(args.gold_sample).read_text(encoding="utf-8"))
    ids = [str(x) for x in gold["instance_ids"]]

    rows = json.loads(Path(args.official).read_text(encoding="utf-8"))["rows"]
    by_id = {
        r["instance_id"]: r
        for r in rows
        if r.get("method") == "cr_guided" and r.get("instance_id") in set(ids)
    }
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise SystemExit(f"Missing CR-guided rows for: {missing}")

    pred_rows = [
        {
            "instance_id": iid,
            "model_name_or_path": "commscm-vi-b-cr_guided",
            "model_patch": by_id[iid].get("model_patch") or "",
        }
        for iid in ids
    ]
    pred_dir = Path("results/oracle_gold_predictions")
    pred_dir.mkdir(parents=True, exist_ok=True)
    pred_path = pred_dir / f"{args.run_id}.jsonl"
    write_predictions_jsonl(pred_rows, pred_path, normalize=True)

    print(f"CR-guided sample n={len(ids)} run_id={args.run_id}", flush=True)
    print(f"instance_ids={ids}", flush=True)

    t0 = time.time()
    eval_out = run_official_evaluation(
        predictions_path=pred_path,
        run_id=args.run_id,
        instance_ids=ids,
        timeout=args.timeout,
        max_workers=args.max_workers,
        namespace="swebench",
    )
    elapsed = time.time() - t0
    report = eval_out.get("report") or load_harness_report(
        args.run_id, predictions_stem=pred_path.stem
    )
    resolved_ids = set(str(x) for x in (report or {}).get("resolved_ids") or [])
    unresolved_ids = set(str(x) for x in (report or {}).get("unresolved_ids") or [])
    error_ids = set(str(x) for x in (report or {}).get("error_ids") or [])

    per = []
    for iid in ids:
        if iid in resolved_ids:
            status, r1 = "resolved", 1.0
        elif iid in error_ids:
            status, r1 = "error", 0.0
        elif iid in unresolved_ids:
            status, r1 = "unresolved", 0.0
        else:
            status, r1 = "missing", None
        per.append(
            {
                "instance_id": iid,
                "status": status,
                "resolve_at_1": r1,
                "hit_gold_edge": by_id[iid].get("hit_gold_edge"),
                "edit_key": by_id[iid].get("edit_key"),
                "patch_len": len(by_id[iid].get("model_patch") or ""),
            }
        )

    scored = [p for p in per if p["resolve_at_1"] is not None]
    mean_r = sum(p["resolve_at_1"] for p in scored) / len(scored) if scored else None
    payload = {
        "experiment": "cr_guided_sample_lf_rescore",
        "note": "VI.B CR-guided synthesized patches rescored with LF-fixed eval.sh",
        "n": len(ids),
        "sample_seed_from_gold": gold.get("sample_seed"),
        "instance_ids": ids,
        "run_id": args.run_id,
        "elapsed_s": round(elapsed, 1),
        "harness_returncode": eval_out.get("returncode"),
        "counts": {
            "resolved": sum(1 for p in per if p["status"] == "resolved"),
            "unresolved": sum(1 for p in per if p["status"] == "unresolved"),
            "error": sum(1 for p in per if p["status"] == "error"),
            "missing": sum(1 for p in per if p["status"] == "missing"),
        },
        "resolve_at_1_mean": mean_r,
        "per_instance": per,
    }
    Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("n", "counts", "resolve_at_1_mean", "elapsed_s")}, indent=2))
    print(f"Wrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
