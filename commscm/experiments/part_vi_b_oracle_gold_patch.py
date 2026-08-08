"""
Oracle gold-patch control (additive eval only — no CommSCM core changes).

Corrected framing: substitute dataset ``patch`` as ``model_patch`` for the
locked VI.B instance IDs; score official Resolve@1. Not tied to CR edge locus.

Sample mode (default): random subset of the locked 100 for host/harness baseline.
Full mode: all 100 — only after sample baseline is reviewed.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

from commscm.adapters.swebench.load import load_swebench_verified_by_ids
from commscm.adapters.swebench.official_eval import (
    load_harness_report,
    run_official_evaluation,
    write_predictions_jsonl,
)


def _load_locked_ids(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [str(x) for x in data["instance_ids"]]


def _sample_ids(ids: list[str], n: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    pool = list(ids)
    rng.shuffle(pool)
    return pool[:n]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--instance-list",
        default="results/part_vi_b_instance_list.json",
    )
    ap.add_argument(
        "--mode",
        choices=("sample", "full"),
        default="sample",
        help="sample = random subset of locked 100; full = all 100",
    )
    ap.add_argument("--sample-n", type=int, default=10)
    ap.add_argument(
        "--sample-seed",
        type=int,
        default=7,
        help="RNG seed for sampling from locked list (not VI.B selection seed)",
    )
    ap.add_argument("--max-workers", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument(
        "--out",
        default="",
        help="Results JSON path (default depends on mode)",
    )
    ap.add_argument("--run-id", default="")
    args = ap.parse_args()

    locked = _load_locked_ids(Path(args.instance_list))
    if args.mode == "sample":
        ids = _sample_ids(locked, args.sample_n, args.sample_seed)
        run_id = args.run_id or f"oracle_gold_sample_n{len(ids)}_s{args.sample_seed}"
        out_path = Path(args.out or f"results/oracle_gold_patch_sample.json")
    else:
        ids = locked
        run_id = args.run_id or "oracle_gold_full_n100"
        out_path = Path(args.out or "results/oracle_gold_patch_full.json")

    print(f"mode={args.mode} n={len(ids)} run_id={run_id}", flush=True)
    print(f"instance_ids={ids}", flush=True)

    instances = load_swebench_verified_by_ids(ids, truncate_problem=False)
    by_id = {inst.instance_id: inst for inst in instances}

    pred_rows: list[dict[str, str]] = []
    meta_rows: list[dict] = []
    for iid in ids:
        inst = by_id[iid]
        patch = inst.gold_patch or ""
        pred_rows.append(
            {
                "instance_id": iid,
                "model_name_or_path": "commscm-oracle-gold",
                "model_patch": patch,
            }
        )
        meta_rows.append(
            {
                "instance_id": iid,
                "repo": inst.repo,
                "gold_patch_len": len(patch),
                "gold_patch_nonempty": bool(patch.strip()),
                "fail_to_pass_n": len(inst.fail_to_pass),
            }
        )

    pred_dir = Path("results/oracle_gold_predictions")
    pred_dir.mkdir(parents=True, exist_ok=True)
    pred_path = pred_dir / f"{run_id}.jsonl"
    # Gold patches are already valid unified diffs — still normalize path prefixes
    write_predictions_jsonl(pred_rows, pred_path, normalize=True)

    t0 = time.time()
    eval_out = run_official_evaluation(
        predictions_path=pred_path,
        run_id=run_id,
        instance_ids=ids,
        timeout=args.timeout,
        max_workers=args.max_workers,
        namespace="swebench",
    )
    elapsed = time.time() - t0

    report = eval_out.get("report") or load_harness_report(
        run_id, predictions_stem=pred_path.stem
    )
    resolved_ids = set(str(x) for x in (report or {}).get("resolved_ids") or [])
    unresolved_ids = set(str(x) for x in (report or {}).get("unresolved_ids") or [])
    error_ids = set(str(x) for x in (report or {}).get("error_ids") or [])

    per_instance = []
    for iid in ids:
        if iid in resolved_ids:
            status = "resolved"
            resolve_at_1 = 1.0
        elif iid in error_ids:
            status = "error"
            resolve_at_1 = 0.0
        elif iid in unresolved_ids:
            status = "unresolved"
            resolve_at_1 = 0.0
        else:
            status = "missing"
            resolve_at_1 = None
        per_instance.append(
            {
                "instance_id": iid,
                "status": status,
                "resolve_at_1": resolve_at_1,
            }
        )

    n = len(ids)
    n_res = sum(1 for r in per_instance if r["status"] == "resolved")
    n_un = sum(1 for r in per_instance if r["status"] == "unresolved")
    n_err = sum(1 for r in per_instance if r["status"] == "error")
    n_miss = sum(1 for r in per_instance if r["status"] == "missing")
    scored = [r for r in per_instance if r["resolve_at_1"] is not None]
    mean_r = (sum(r["resolve_at_1"] for r in scored) / len(scored)) if scored else None

    payload = {
        "experiment": "oracle_gold_patch_control",
        "framing": (
            "dataset gold patch substituted as model_patch; "
            "not tied to CR communication-edge location"
        ),
        "mode": args.mode,
        "n": n,
        "sample_seed": args.sample_seed if args.mode == "sample" else None,
        "instance_list": args.instance_list,
        "instance_ids": ids,
        "run_id": run_id,
        "predictions_path": str(pred_path),
        "max_workers": args.max_workers,
        "elapsed_s": round(elapsed, 1),
        "harness_returncode": eval_out.get("returncode"),
        "counts": {
            "resolved": n_res,
            "unresolved": n_un,
            "error": n_err,
            "missing": n_miss,
        },
        "resolve_at_1_mean": mean_r,
        "per_instance": per_instance,
        "instance_meta": meta_rows,
        "harness_report_keys": sorted((report or {}).keys()) if report else [],
        "eval_meta_path": str(pred_dir / f"{run_id}_eval_meta.json"),
    }
    (pred_dir / f"{run_id}_eval_meta.json").write_text(
        json.dumps(eval_out, indent=2, default=str), encoding="utf-8"
    )
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in (
        "mode", "n", "counts", "resolve_at_1_mean", "elapsed_s", "instance_ids"
    )}, indent=2), flush=True)
    print(f"Wrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
