"""
Resume Part VI.B Docker rescore without redoing finished patch-apply errors.

- Re-runs: incomplete/hung instances + the last 2 unresolved (sklearn, possibly WiFi)
- Skips: prior unresolved (older django reports) and apply-error logs (via report stubs)
- Then continues remaining methods (reward_only, random, static_heuristic)

Does not change CommSCM core / prereg instance list.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from commscm.adapters.swebench.official_eval import (
    evaluate_by_method,
    normalize_model_patch,
    resolve_map_from_report,
    run_official_evaluation,
    write_predictions_jsonl,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "part_vi_b_official.json"
PRED_DIR = ROOT / "results" / "part_vi_b_predictions"
LOG_ROOT = (
    ROOT
    / "logs/run_evaluation/vi_b_rescore_part_vi_b_official_cr_guided/commscm-vi-b-cr_guided"
)
RUN_ID = "vi_b_rescore_part_vi_b_official_cr_guided"
MODEL = "commscm-vi-b-cr_guided"

# Last two unresolved from this restart (2026-08-04 ~02:34) — re-include
RERUN_UNRESOLVED = [
    "scikit-learn__scikit-learn-14710",
    "scikit-learn__scikit-learn-14894",
]


def _classify(ids: list[str]) -> tuple[list[str], list[str], list[str]]:
    incomplete: list[str] = []
    unresolved: list[str] = []
    errors: list[str] = []
    for iid in ids:
        d = LOG_ROOT / iid
        log = d / "run_instance.log"
        rep = d / "report.json"
        size = log.stat().st_size if log.exists() else 0
        if size == 0:
            incomplete.append(iid)
            continue
        if rep.exists():
            unresolved.append(iid)
            continue
        errors.append(iid)
    return incomplete, unresolved, errors


def _stub_error_reports(error_ids: list[str]) -> int:
    """Write report.json so harness skips apply-failures (not re-run)."""
    n = 0
    for iid in error_ids:
        d = LOG_ROOT / iid
        d.mkdir(parents=True, exist_ok=True)
        rep = d / "report.json"
        if rep.exists():
            continue
        payload = {
            iid: {
                "patch_is_None": False,
                "patch_exists": True,
                "patch_successfully_applied": False,
                "resolved": False,
                "tests_status": {
                    "FAIL_TO_PASS": {"success": [], "failure": []},
                    "PASS_TO_PASS": {"success": [], "failure": []},
                },
                "commscm_skip_stub": True,
                "commscm_note": "stub so resume skips prior patch-apply error",
            }
        }
        rep.write_text(json.dumps(payload, indent=4), encoding="utf-8")
        n += 1
    return n


def _clear_instance(iid: str) -> None:
    d = LOG_ROOT / iid
    if d.exists():
        shutil.rmtree(d)


def _resolve_map_from_logs() -> dict[str, bool]:
    """Build resolve map from per-instance report.json files."""
    out: dict[str, bool] = {}
    if not LOG_ROOT.exists():
        return out
    for d in LOG_ROOT.iterdir():
        if not d.is_dir():
            continue
        rep = d / "report.json"
        if not rep.exists():
            # nonempty error log without report → unresolved/error = False
            log = d / "run_instance.log"
            if log.exists() and log.stat().st_size > 0:
                out[d.name] = False
            continue
        try:
            rj = json.loads(rep.read_text(encoding="utf-8"))
            entry = rj.get(d.name, rj)
            if isinstance(entry, dict) and "resolved" in entry:
                if entry.get("commscm_skip_stub"):
                    out[d.name] = False
                else:
                    out[d.name] = bool(entry.get("resolved"))
        except Exception:  # noqa: BLE001
            out[d.name] = False
    return out


def main() -> None:
    if not OUT.exists():
        raise SystemExit(f"Missing {OUT}")
    payload = json.loads(OUT.read_text(encoding="utf-8"))
    rows = list(payload.get("rows") or [])
    cr_ids = [r["instance_id"] for r in rows if r["method"] == "cr_guided"]

    incomplete, unresolved, errors = _classify(cr_ids)
    # Only re-run the last-two unresolved (wifi concern); keep older unresolved skipped
    rerun_unresolved = [i for i in RERUN_UNRESOLVED if i in unresolved or i in cr_ids]
    to_rerun = sorted(set(incomplete + rerun_unresolved))

    print(
        f"cr_guided classify: errors={len(errors)} unresolved_reports={len(unresolved)} "
        f"incomplete={len(incomplete)}",
        flush=True,
    )
    print(f"Will re-run ({len(to_rerun)}): {to_rerun}", flush=True)

    n_stub = _stub_error_reports(errors)
    print(f"Wrote skip stubs for {n_stub} prior apply-errors", flush=True)

    for iid in to_rerun:
        _clear_instance(iid)
        print(f"  cleared {iid}", flush=True)

    # Predictions for re-run only
    pred_rows = []
    for r in rows:
        if r["method"] != "cr_guided" or r["instance_id"] not in to_rerun:
            continue
        patch = normalize_model_patch(r.get("model_patch") or "")
        if not patch.strip():
            continue
        pred_rows.append(
            {
                "instance_id": r["instance_id"],
                "model_name_or_path": MODEL,
                "model_patch": patch,
            }
        )

    if pred_rows:
        pred_path = PRED_DIR / f"{RUN_ID}_resume.jsonl"
        write_predictions_jsonl(pred_rows, pred_path, normalize=True)
        print(
            f"Docker resume cr_guided n={len(pred_rows)} workers=4 ...",
            flush=True,
        )
        eval_out = run_official_evaluation(
            predictions_path=pred_path,
            run_id=RUN_ID,
            instance_ids=[p["instance_id"] for p in pred_rows],
            timeout=1800,
            max_workers=4,
            namespace="swebench",
        )
        (PRED_DIR / f"{RUN_ID}_resume_eval_meta.json").write_text(
            json.dumps(eval_out, indent=2), encoding="utf-8"
        )
        print(f"cr_guided resume returncode={eval_out.get('returncode')}", flush=True)
    else:
        print("Nothing to re-run for cr_guided", flush=True)

    # Merge cr_guided resolve from all logs
    rmap = _resolve_map_from_logs()
    for r in rows:
        if r["method"] != "cr_guided":
            continue
        if r["instance_id"] in rmap:
            r["resolve_at_1"] = 1.0 if rmap[r["instance_id"]] else 0.0
            r["docker_eval"] = {"rescore": True, "resume": True, "resolved_known": True}

    # Remaining methods full eval
    other_preds = []
    for r in rows:
        if r["method"] == "cr_guided":
            continue
        patch = normalize_model_patch(r.get("model_patch") or "")
        if not patch.strip():
            continue
        other_preds.append(
            {
                "instance_id": r["instance_id"],
                "model_name_or_path": f"commscm-vi-b-{r['method']}",
                "model_patch": patch,
            }
        )

    print(f"Docker remaining methods n_preds={len(other_preds)} ...", flush=True)
    results = evaluate_by_method(
        other_preds,
        run_id_prefix="vi_b_rescore_part_vi_b_official",
        pred_dir=PRED_DIR,
        max_workers=4,
        timeout=1800,
        namespace="swebench",
    )
    for r in rows:
        if r["method"] == "cr_guided":
            continue
        ev = results.get(r["method"])
        if not ev:
            continue
        smap = ev.get("resolve_map") or resolve_map_from_report(ev.get("report"))
        if r["instance_id"] in smap:
            r["resolve_at_1"] = 1.0 if smap[r["instance_id"]] else 0.0
        r["docker_run_id"] = ev.get("run_id")
        r["docker_eval"] = {
            "returncode": ev.get("returncode"),
            "resolved_known": r["instance_id"] in smap,
            "rescore": True,
            "resume": True,
        }

    meta = {
        **payload,
        "partial": True,
        "docker_rescored": True,
        "docker_resume": True,
        "docker_resume_rerun_ids": to_rerun,
        "core_unchanged": True,
    }
    OUT.write_text(json.dumps({**meta, "rows": rows}, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}", flush=True)


if __name__ == "__main__":
    # ensure cwd is repo root
    import os

    os.chdir(ROOT)
    main()
