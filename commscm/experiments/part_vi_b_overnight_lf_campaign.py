"""
Overnight LF-fixed Docker campaign (no CommSCM core changes).

Batched design (disk-aware):
  For each batch of instance IDs:
    1) oracle gold
    2) VI.B methods: cr_guided, reward_only, random, static_heuristic
    using cache_level=instance so images are pulled once per batch
    3) prune sweb.eval images before next batch

Then write CR-guided apply-failure taxonomy + final rollups.
Resume-safe via per-instance report.json (harness exclude_completed).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from collections import Counter
from pathlib import Path

from commscm.adapters.swebench.load import load_swebench_verified_by_ids
from commscm.adapters.swebench.official_eval import (
    load_harness_report,
    run_official_evaluation,
    write_predictions_jsonl,
)


INSTANCE_LIST = Path("results/part_vi_b_instance_list.json")
OFFICIAL = Path("results/part_vi_b_official.json")
PRED_DIR = Path("results/part_vi_b_predictions_lf")
OUT_DIR = Path("results")
METHODS = ("cr_guided", "reward_only", "random", "static_heuristic")

GOLD_RUN = "oracle_gold_full_n100_lf"
GOLD_MODEL = "commscm-oracle-gold"
GOLD_OUT = OUT_DIR / "oracle_gold_patch_full_lf.json"
VI_B_SUMMARY = OUT_DIR / "part_vi_b_lf_rescore_summary.json"
TAX_OUT = OUT_DIR / "part_vi_b_lf_cr_guided_failure_taxonomy.json"
CHECKPOINT = OUT_DIR / "overnight_lf_campaign_checkpoint.json"
LOCK_FILE = OUT_DIR / "overnight_lf_campaign.lock"

# Pre-pull via docker CLI (sequential) — docker-py concurrent pulls hang on this host.
# After images are local, workers=2 is safe for eval.
BATCH_SIZE = 8
MAX_WORKERS = 2
MIN_FREE_GB = 16.0
NAMESPACE = "swebench"
ARCH = "x86_64"


def _instance_image_tag(instance_id: str) -> str:
    # Matches swebench TestSpec.instance_image_key for remote namespace images.
    key = f"sweb.eval.{ARCH}.{instance_id.lower()}:latest"
    return f"{NAMESPACE}/{key}".replace("__", "_1776_")


def _prepull_images(ids: list[str]) -> None:
    """Pull eval images via docker CLI one-by-one (avoids docker-py hang)."""
    for iid in ids:
        tag = _instance_image_tag(iid)
        # Skip if already present.
        probe = subprocess.run(
            ["docker", "image", "inspect", tag],
            capture_output=True,
            text=True,
        )
        if probe.returncode == 0:
            print(f"[prepull] have {tag}", flush=True)
            continue
        _ensure_disk()
        print(f"[prepull] pulling {tag} (free_gb={_free_gb():.1f})...", flush=True)
        t0 = time.time()
        r = subprocess.run(
            ["docker", "pull", tag],
            capture_output=True,
            text=True,
            errors="replace",
        )
        elapsed = round(time.time() - t0, 1)
        if r.returncode != 0:
            print(
                f"[prepull] FAIL {tag} rc={r.returncode} "
                f"stderr={((r.stderr or '')[-400:])}",
                flush=True,
            )
        else:
            print(f"[prepull] ok {tag} in {elapsed}s", flush=True)


def _acquire_lock() -> None:
    """Fail fast if another overnight campaign is already running."""
    import os

    if LOCK_FILE.exists():
        try:
            old = int(LOCK_FILE.read_text(encoding="utf-8").strip().split()[0])
            # Windows: OpenProcess check via os.kill(pid, 0) doesn't work; use tasklist.
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {old}", "/NH"],
                capture_output=True,
                text=True,
            )
            if str(old) in out.stdout and "python" in out.stdout.lower():
                raise SystemExit(
                    f"Another campaign holds lock pid={old} ({LOCK_FILE}). Aborting."
                )
        except SystemExit:
            raise
        except Exception:
            pass
    LOCK_FILE.write_text(f"{os.getpid()} {time.time()}\n", encoding="utf-8")


def _release_lock() -> None:
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def _load_ids() -> list[str]:
    return [str(x) for x in json.loads(INSTANCE_LIST.read_text(encoding="utf-8"))["instance_ids"]]


def _chunks(xs: list[str], n: int) -> list[list[str]]:
    return [xs[i : i + n] for i in range(0, len(xs), n)]


def _free_gb() -> float:
    return shutil.disk_usage(".").free / 1e9


def _prune_eval_images() -> None:
    """Remove SWE-bench eval instance images to free disk between batches."""
    print(f"[disk] before prune free_gb={_free_gb():.1f}", flush=True)
    try:
        out = subprocess.check_output(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
            text=True,
            errors="replace",
        )
    except Exception as exc:
        print(f"[disk] docker images failed: {exc}", flush=True)
        return
    removed = 0
    for line in out.splitlines():
        tag = line.strip()
        if not tag or tag.endswith(":<none>"):
            continue
        # Remote namespace images look like swebench/sweb.eval.x86_64....
        if "sweb.eval" not in tag:
            continue
        r = subprocess.run(
            ["docker", "rmi", "-f", tag],
            capture_output=True,
            text=True,
        )
        if r.returncode == 0:
            removed += 1
    subprocess.run(
        ["docker", "system", "prune", "-f"],
        capture_output=True,
        text=True,
    )
    print(f"[disk] removed {removed} sweb.eval images; free_gb={_free_gb():.1f}", flush=True)


def _ensure_disk() -> None:
    if _free_gb() < MIN_FREE_GB:
        _prune_eval_images()
        if _free_gb() < 12.0:
            subprocess.run(
                ["docker", "system", "prune", "-af"],
                capture_output=True,
                text=True,
            )
            print(f"[disk] hard prune free_gb={_free_gb():.1f}", flush=True)


def _summarize_from_logs(run_id: str, model: str, ids: list[str]) -> dict:
    """Aggregate per-instance report.json under logs/run_evaluation."""
    root = Path("logs/run_evaluation") / run_id / model
    resolved, unresolved, errors, missing = [], [], [], []
    per = []
    for iid in ids:
        report_path = root / iid / "report.json"
        if not report_path.exists():
            # Incomplete / harness error often leaves run_instance.log only.
            log_path = root / iid / "run_instance.log"
            if log_path.exists() and log_path.stat().st_size > 0:
                text = log_path.read_text(encoding="utf-8", errors="replace")
                if "ERROR" in text or "Error" in text or "Failed" in text:
                    errors.append(iid)
                    per.append({"instance_id": iid, "status": "error", "resolve_at_1": 0.0})
                    continue
            missing.append(iid)
            per.append({"instance_id": iid, "status": "missing", "resolve_at_1": None})
            continue
        try:
            rep = json.loads(report_path.read_text(encoding="utf-8"))
            entry = rep.get(iid) or next(iter(rep.values()))
            ok = bool(entry.get("resolved"))
        except Exception:
            errors.append(iid)
            per.append({"instance_id": iid, "status": "error", "resolve_at_1": 0.0})
            continue
        if ok:
            resolved.append(iid)
            per.append({"instance_id": iid, "status": "resolved", "resolve_at_1": 1.0})
        else:
            unresolved.append(iid)
            per.append({"instance_id": iid, "status": "unresolved", "resolve_at_1": 0.0})

    scored = [p for p in per if p["resolve_at_1"] is not None]
    mean = sum(p["resolve_at_1"] for p in scored) / len(scored) if scored else None
    return {
        "counts": {
            "resolved": len(resolved),
            "unresolved": len(unresolved),
            "error": len(errors),
            "missing": len(missing),
            "scored": len(scored),
        },
        "resolve_at_1_mean": mean,
        "per_instance": per,
        "resolved_ids": sorted(resolved),
        "unresolved_ids": sorted(unresolved),
        "error_ids": sorted(errors),
        "missing_ids": sorted(missing),
    }


def _method_run_id(method: str) -> str:
    return f"vi_b_lf_rescore_{method}"


def _method_model(method: str) -> str:
    return f"commscm-vi-b-{method}"


def _instance_done(root: Path, iid: str) -> bool:
    """True if harness wrote report.json OR a conclusive error log (apply fail)."""
    if (root / iid / "report.json").exists():
        return True
    log_path = root / iid / "run_instance.log"
    if not log_path.exists() or log_path.stat().st_size < 50:
        return False
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False
    markers = (
        "Patch Apply Failed",
        "APPLY_PATCH_FAIL",
        "EvaluationError",
        "Error building",
        "Error pulling",
        "report.json",
    )
    # Conclusive failure: patch never applied / build failed. Incomplete pulls
    # (empty or pull-only) return False so they retry.
    if any(m in text for m in markers):
        # Write a lightweight marker so future resets keep this dir.
        marker = root / iid / "commscm_error_marker.json"
        if not marker.exists():
            marker.write_text(
                json.dumps({"instance_id": iid, "status": "error"}),
                encoding="utf-8",
            )
        return True
    return False


def _completed_ids(run_id: str, model: str, ids: list[str]) -> set[str]:
    root = Path("logs/run_evaluation") / run_id / model
    return {iid for iid in ids if _instance_done(root, iid)}


def _write_checkpoint(state: dict) -> None:
    CHECKPOINT.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _run_condition(
    *,
    label: str,
    run_id: str,
    model: str,
    ids_batch: list[str],
    preds_by_id: dict[str, str],
) -> None:
    todo = [i for i in ids_batch if i not in _completed_ids(run_id, model, ids_batch)]
    if not todo:
        print(f"  [{label}] batch already complete ({len(ids_batch)})", flush=True)
        return
    _ensure_disk()
    print(
        f"  [{label}] evaluating {len(todo)}/{len(ids_batch)} "
        f"(free_gb={_free_gb():.1f})",
        flush=True,
    )
    preds = [
        {
            "instance_id": iid,
            "model_name_or_path": model,
            "model_patch": preds_by_id[iid],
        }
        for iid in todo
    ]
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    pred_path = PRED_DIR / f"{run_id}_batch.jsonl"
    write_predictions_jsonl(preds, pred_path, normalize=True)
    eval_out = run_official_evaluation(
        predictions_path=pred_path,
        run_id=run_id,
        instance_ids=todo,
        timeout=1800,
        max_workers=MAX_WORKERS,
        namespace="swebench",
        cache_level="instance",
        clean=False,
    )
    print(
        f"  [{label}] harness rc={eval_out.get('returncode')} "
        f"free_gb={_free_gb():.1f}",
        flush=True,
    )


def phase_batched_campaign(ids: list[str]) -> None:
    print(
        f"\n=== BATCHED CAMPAIGN n={len(ids)} batch_size={BATCH_SIZE} "
        f"workers={MAX_WORKERS} ===",
        flush=True,
    )
    instances = load_swebench_verified_by_ids(ids, truncate_problem=False)
    gold_by_id = {i.instance_id: (i.gold_patch or "") for i in instances}

    rows = json.loads(OFFICIAL.read_text(encoding="utf-8"))["rows"]
    method_patches: dict[str, dict[str, str]] = {m: {} for m in METHODS}
    for r in rows:
        m = r.get("method")
        if m in method_patches:
            method_patches[m][r["instance_id"]] = r.get("model_patch") or ""

    batches = _chunks(ids, BATCH_SIZE)
    state = {
        "started_at": time.time(),
        "n": len(ids),
        "batch_size": BATCH_SIZE,
        "batches_total": len(batches),
        "batches_done": 0,
    }
    _write_checkpoint(state)

    for bi, batch in enumerate(batches):
        print(
            f"\n=== BATCH {bi + 1}/{len(batches)} "
            f"ids={batch[0]}..{batch[-1]} ({len(batch)}) ===",
            flush=True,
        )
        # Pull images via CLI first — prevents docker-py hang on this Windows host.
        need_pull = [
            iid
            for iid in batch
            if iid
            not in _completed_ids(GOLD_RUN, GOLD_MODEL, batch)
            or any(
                iid
                not in _completed_ids(_method_run_id(m), _method_model(m), batch)
                for m in METHODS
            )
        ]
        if need_pull:
            _prepull_images(need_pull)
        _run_condition(
            label="oracle_gold",
            run_id=GOLD_RUN,
            model=GOLD_MODEL,
            ids_batch=batch,
            preds_by_id=gold_by_id,
        )
        for method in METHODS:
            _run_condition(
                label=method,
                run_id=_method_run_id(method),
                model=_method_model(method),
                ids_batch=batch,
                preds_by_id=method_patches[method],
            )
        # Free disk before next batch pulls.
        _prune_eval_images()
        state["batches_done"] = bi + 1
        state["last_batch_ids"] = batch
        state["free_gb"] = round(_free_gb(), 2)
        # Partial rollups for morning visibility.
        gold_partial = _summarize_from_logs(GOLD_RUN, GOLD_MODEL, ids)
        state["oracle_gold_partial"] = {
            "resolve_at_1_mean": gold_partial["resolve_at_1_mean"],
            "counts": gold_partial["counts"],
        }
        state["vi_b_partial"] = {}
        for method in METHODS:
            s = _summarize_from_logs(
                _method_run_id(method), _method_model(method), ids
            )
            state["vi_b_partial"][method] = {
                "resolve_at_1_mean": s["resolve_at_1_mean"],
                "counts": s["counts"],
            }
        _write_checkpoint(state)
        print(
            f"BATCH {bi + 1} done; gold_partial={state['oracle_gold_partial']}",
            flush=True,
        )


def finalize(ids: list[str]) -> dict:
    gold = _summarize_from_logs(GOLD_RUN, GOLD_MODEL, ids)
    gold_payload = {
        "experiment": "oracle_gold_full_n100_lf",
        "framing": "dataset gold patch as model_patch; LF-fixed harness; batched",
        "n": len(ids),
        "selection_seed": 42,
        "run_id": GOLD_RUN,
        **gold,
    }
    GOLD_OUT.write_text(json.dumps(gold_payload, indent=2), encoding="utf-8")

    by_method = {}
    for method in METHODS:
        s = _summarize_from_logs(
            _method_run_id(method), _method_model(method), ids
        )
        payload = {
            "method": method,
            "run_id": _method_run_id(method),
            "n": len(ids),
            **s,
        }
        (OUT_DIR / f"part_vi_b_lf_rescore_{method}.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
        by_method[method] = {
            "resolve_at_1_mean": s["resolve_at_1_mean"],
            "counts": s["counts"],
        }
    aggregate = {
        "experiment": "part_vi_b_lf_rescore_all_methods",
        "note": "Supersedes CRLF-era VI.B Resolve@1; patches from original LLM run",
        "n": len(ids),
        "selection_seed": 42,
        "by_method": by_method,
    }
    VI_B_SUMMARY.write_text(json.dumps(aggregate, indent=2), encoding="utf-8")
    return {"gold": gold_payload, "vi_b": aggregate}


_PATH_RE = re.compile(
    r"can't find file to patch|No such file or directory|No file to patch",
    re.I,
)
_MALFORMED_RE = re.compile(r"malformed patch|corrupt patch|unexpected end of file", re.I)
_HUNK_RE = re.compile(r"hunk FAILED|while searching for|fuzz|REJECT", re.I)


def _categorize_log(text: str) -> str:
    if _PATH_RE.search(text):
        return "wrong_file_path"
    if _MALFORMED_RE.search(text):
        return "invalid_unified_diff_syntax"
    if _HUNK_RE.search(text):
        return "wrong_context_hunk_mismatch"
    if "Patch Apply Failed" in text or "APPLY_PATCH_FAIL" in text:
        return "patch_apply_other"
    if "pipefail\r" in text or "activate\r" in text:
        return "crlf_eval_sh"
    return "other_or_unknown"


def phase_cr_failure_taxonomy(ids: list[str]) -> dict:
    print("\n=== CR-guided patch-apply taxonomy ===", flush=True)
    log_root = Path("logs/run_evaluation") / _method_run_id("cr_guided") / _method_model(
        "cr_guided"
    )
    official_rows = {
        r["instance_id"]: r
        for r in json.loads(OFFICIAL.read_text(encoding="utf-8"))["rows"]
        if r.get("method") == "cr_guided"
    }
    cr_summary = _summarize_from_logs(
        _method_run_id("cr_guided"), _method_model("cr_guided"), ids
    )
    details = []
    cats: Counter[str] = Counter()
    for iid in ids:
        status = next(
            (p["status"] for p in cr_summary["per_instance"] if p["instance_id"] == iid),
            "missing",
        )
        log_path = log_root / iid / "run_instance.log"
        text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        if status == "resolved":
            cat = "resolved"
        elif status == "unresolved":
            cat = "applied_tests_fail"
        elif status == "error":
            cat = _categorize_log(text) if text else "error_no_log"
        else:
            cat = "missing"
        cats[cat] += 1
        row = official_rows.get(iid, {})
        details.append(
            {
                "instance_id": iid,
                "status": status,
                "failure_category": cat,
                "hit_gold_edge": row.get("hit_gold_edge"),
                "edit_key": row.get("edit_key"),
                "patch_len": len(row.get("model_patch") or ""),
                "log_snippet": "\n".join(text.splitlines()[-40:]) if text else "",
            }
        )

    apply_buckets = {
        "wrong_path": cats.get("wrong_file_path", 0),
        "malformed_diff": cats.get("invalid_unified_diff_syntax", 0),
        "hunk_mismatch": cats.get("wrong_context_hunk_mismatch", 0),
        "other_apply": (
            cats.get("patch_apply_other", 0)
            + cats.get("error_no_log", 0)
            + cats.get("other_or_unknown", 0)
            + cats.get("crlf_eval_sh", 0)
        ),
        "resolved": cats.get("resolved", 0),
        "applied_tests_fail": cats.get("applied_tests_fail", 0),
        "missing": cats.get("missing", 0),
    }
    payload = {
        "experiment": "cr_guided_lf_patch_apply_taxonomy",
        "n": len(ids),
        "category_counts": dict(cats),
        "apply_failure_buckets": apply_buckets,
        "among_errors_hit_gold_edge": sum(
            1 for d in details if d["status"] == "error" and d.get("hit_gold_edge")
        ),
        "details": details,
    }
    TAX_OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"taxonomy buckets={apply_buckets}", flush=True)
    return payload


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ids = _load_ids()
    assert len(ids) == 100, len(ids)
    t0 = time.time()
    try:
        phase_batched_campaign(ids)
        results = finalize(ids)
        tax = phase_cr_failure_taxonomy(ids)
    except Exception as exc:
        _write_checkpoint(
            {
                "error": repr(exc),
                "failed_at": time.time(),
                "elapsed_s": round(time.time() - t0, 1),
            }
        )
        raise

    elapsed = round(time.time() - t0, 1)
    final = {
        "oracle_gold_resolve_at_1": results["gold"]["resolve_at_1_mean"],
        "oracle_gold_counts": results["gold"]["counts"],
        "vi_b_by_method": results["vi_b"]["by_method"],
        "cr_guided_failure_taxonomy": tax["apply_failure_buckets"],
        "cr_guided_category_counts_raw": tax["category_counts"],
        "elapsed_s": elapsed,
        "artifacts": {
            "oracle": str(GOLD_OUT),
            "vi_b_summary": str(VI_B_SUMMARY),
            "cr_taxonomy": str(TAX_OUT),
            "checkpoint": str(CHECKPOINT),
        },
    }
    final_path = OUT_DIR / "overnight_lf_campaign_final.json"
    final_path.write_text(json.dumps(final, indent=2), encoding="utf-8")

    lines = [
        "# Overnight LF-fixed campaign results",
        "",
        f"Elapsed_s: {elapsed}",
        "",
        "## Oracle gold n=100",
        f"- Resolve@1: **{final['oracle_gold_resolve_at_1']}**",
        f"- Counts: `{final['oracle_gold_counts']}`",
        "",
        "## VI.B LF rescore (supersedes CRLF-era Resolve@1)",
    ]
    for m, v in final["vi_b_by_method"].items():
        lines.append(
            f"- **{m}**: Resolve@1={v['resolve_at_1_mean']} counts={v['counts']}"
        )
    lines += [
        "",
        "## CR-guided failure taxonomy",
        f"`{final['cr_guided_failure_taxonomy']}`",
        "",
        "CommSCM core unchanged. Batched eval with cache_level=instance.",
    ]
    (OUT_DIR / "OVERNIGHT_LF_CAMPAIGN_RESULTS.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(f"\nALL DONE -> {final_path}", flush=True)


def main_with_retries(max_attempts: int = 50) -> None:
    """Outer retry loop so overnight runs resume after transient Docker failures."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _acquire_lock()
    try:
        for attempt in range(1, max_attempts + 1):
            if (OUT_DIR / "overnight_lf_campaign_final.json").exists():
                print("Final artifact already present; exiting.", flush=True)
                return
            print(f"\n#### CAMPAIGN ATTEMPT {attempt}/{max_attempts} ####", flush=True)
            try:
                main()
                return
            except Exception as exc:
                print(f"Attempt {attempt} failed: {exc!r}", flush=True)
                try:
                    out = subprocess.check_output(
                        ["docker", "ps", "-aq"], text=True, errors="replace"
                    )
                    for cid in out.split():
                        subprocess.run(
                            ["docker", "rm", "-f", cid], capture_output=True, text=True
                        )
                except Exception:
                    pass
                if _free_gb() < 12.0:
                    _prune_eval_images()
                time.sleep(20)
        raise RuntimeError(f"Campaign failed after {max_attempts} attempts")
    finally:
        _release_lock()


if __name__ == "__main__":
    main_with_retries()
