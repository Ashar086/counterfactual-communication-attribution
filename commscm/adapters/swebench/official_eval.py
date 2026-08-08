"""
Official SWE-bench Docker resolve@1 helper (Part VI.B harness — not CommSCM core).

Wraps ``swebench.harness.run_evaluation`` at the preregistered harness revision.

IMPORTANT: ``run_evaluation`` collapses predictions by ``instance_id`` (last wins).
Never put multiple methods for the same instance in one predictions file.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def normalize_model_patch(patch: str) -> str:
    """
    Best-effort normalize agent patch text for ``git apply -p1``.

    - LF newlines
    - Ensure ``a/`` ``b/`` prefixes on ---/+++ paths when missing
    - Drop prune-fallback ``apply_patch`` stubs that break unified diffs
    """
    if not patch:
        return ""
    text = patch.replace("\r\n", "\n").replace("\r", "\n").strip() + "\n"
    # Remove soft-null fallback stubs appended after a real hunk
    if "def apply_patch" in text and ("---" in text or "diff " in text):
        # Keep only lines before a malformed non-diff stub that appears after hunk body
        lines = text.splitlines(keepends=True)
        cut = None
        seen_hunk = False
        for i, line in enumerate(lines):
            if line.startswith("@@"):
                seen_hunk = True
            if seen_hunk and line.startswith("def apply_patch"):
                cut = i
                break
        if cut is not None:
            text = "".join(lines[:cut])
            if not text.endswith("\n"):
                text += "\n"

    def _fix_path(line: str, prefix: str) -> str:
        # --- path\t...  or --- path
        m = re.match(r"^(---|\+\+\+)\s+(\S+)", line)
        if not m:
            return line
        kind, path = m.group(1), m.group(2)
        if path in {"/dev/null"}:
            return line
        if path.startswith("a/") or path.startswith("b/"):
            return line
        # already diff --git style handled elsewhere
        return f"{kind} {prefix}{path}" + line[m.end() :]

    out_lines = []
    for line in text.splitlines(keepends=True):
        raw = line.rstrip("\n")
        if raw.startswith("--- "):
            out_lines.append(_fix_path(raw, "a/") + "\n")
        elif raw.startswith("+++ "):
            out_lines.append(_fix_path(raw, "b/") + "\n")
        else:
            out_lines.append(line if line.endswith("\n") else line + "\n")
    return "".join(out_lines)


def write_predictions_jsonl(
    rows: list[dict[str, str]],
    path: Path,
    *,
    normalize: bool = True,
) -> Path:
    """Each row: instance_id, model_name_or_path, model_patch."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            patch = r.get("model_patch") or ""
            if normalize:
                patch = normalize_model_patch(patch)
            rec = {
                "instance_id": r["instance_id"],
                "model_name_or_path": r["model_name_or_path"],
                "model_patch": patch,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return path


def run_official_evaluation(
    *,
    predictions_path: Path,
    run_id: str,
    instance_ids: list[str] | None = None,
    dataset_name: str = "princeton-nlp/SWE-bench_Verified",
    timeout: int = 1800,
    max_workers: int = 4,
    namespace: str = "swebench",
    cache_level: str = "env",
    clean: bool = False,
) -> dict[str, Any]:
    """Invoke official harness; return parsed report summary if present.

    Uses ``commscm.adapters.swebench.run_evaluation_lf`` so ``eval.sh`` is
    written with Unix LF newlines on Windows (E6 CRLF fix). Does not modify
    CommSCM core.

    ``cache_level="instance"`` keeps pulled eval images so a later method can
    rescore the same IDs without re-pulling (needed for overnight batching).
    """
    cmd = [
        sys.executable,
        "-m",
        "commscm.adapters.swebench.run_evaluation_lf",
        "--dataset_name",
        dataset_name,
        "--predictions_path",
        str(predictions_path.resolve()),
        "--max_workers",
        str(max_workers),
        "--run_id",
        run_id,
        "--timeout",
        str(timeout),
        "--namespace",
        namespace,
        "--cache_level",
        cache_level,
        "--clean",
        "true" if clean else "false",
    ]
    if instance_ids:
        cmd.extend(["--instance_ids", *instance_ids])

    # Stream harness logs live (capture_output hides hours of Docker progress).
    log_path = Path("results") / "part_vi_b_predictions" / f"{run_id}_harness.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    chunks: list[str] = []
    with log_path.open("w", encoding="utf-8", errors="replace") as logf:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            logf.write(line)
            logf.flush()
            chunks.append(line)
            if len(chunks) > 5000:
                chunks = chunks[-2000:]
        returncode = proc.wait()
    joined = "".join(chunks)
    out: dict[str, Any] = {
        "returncode": returncode,
        "stdout_tail": joined[-4000:],
        "stderr_tail": "",
        "harness_log": str(log_path),
        "run_id": run_id,
        "predictions_path": str(predictions_path),
    }

    candidates = list(Path(".").glob(f"**/*{run_id}*.json"))
    if Path("logs").exists():
        candidates += list(Path("logs").glob(f"**/*{run_id}*"))
    out["artifact_candidates"] = [str(p) for p in candidates[:20]]

    report = load_harness_report(run_id, predictions_stem=predictions_path.stem)
    if report:
        out["report"] = report
    return out


def evaluate_by_method(
    pending: list[dict[str, str]],
    *,
    run_id_prefix: str,
    pred_dir: Path,
    max_workers: int = 4,
    timeout: int = 1800,
    namespace: str = "swebench",
) -> dict[str, dict[str, Any]]:
    """
    Run one official eval **per method**.

    Required because swebench ``run_evaluation`` does:
    ``predictions = {instance_id: pred for pred in predictions}`` (last wins).
    """
    by_method: dict[str, list[dict[str, str]]] = {}
    for p in pending:
        method = p["model_name_or_path"].rsplit("-", 1)[-1]
        # model_name_or_path is commscm-vi-b-{method}
        if "commscm-vi-b-" in p["model_name_or_path"]:
            method = p["model_name_or_path"].split("commscm-vi-b-", 1)[1]
        by_method.setdefault(method, []).append(p)

    results: dict[str, dict[str, Any]] = {}
    for method, preds in by_method.items():
        # Dedupe instance_id within method (keep last)
        uniq: dict[str, dict[str, str]] = {}
        for p in preds:
            uniq[p["instance_id"]] = p
        preds_u = list(uniq.values())
        run_id = f"{run_id_prefix}_{method}"
        pred_path = pred_dir / f"{run_id}.jsonl"
        write_predictions_jsonl(preds_u, pred_path, normalize=True)
        print(
            f"  Docker resolve@1 method={method} n={len(preds_u)} "
            f"workers={max_workers} ...",
            flush=True,
        )
        eval_out = run_official_evaluation(
            predictions_path=pred_path,
            run_id=run_id,
            instance_ids=[p["instance_id"] for p in preds_u],
            timeout=timeout,
            max_workers=max_workers,
            namespace=namespace,
        )
        report = eval_out.get("report") or load_harness_report(
            run_id, predictions_stem=pred_path.stem
        )
        if report:
            eval_out["report"] = report
        eval_out["resolve_map"] = resolve_map_from_report(report)
        eval_out["error_ids"] = list((report or {}).get("error_ids") or [])
        (pred_dir / f"{run_id}_eval_meta.json").write_text(
            json.dumps(eval_out, indent=2), encoding="utf-8"
        )
        results[method] = eval_out
    return results


def resolve_map_from_report(report: dict[str, Any] | None) -> dict[str, bool]:
    if not report:
        return {}
    resolved: dict[str, bool] = {}
    for i in report.get("resolved_ids") or []:
        resolved[str(i)] = True
    for i in report.get("unresolved_ids") or []:
        resolved.setdefault(str(i), False)
    for i in report.get("error_ids") or []:
        # treat apply/harness errors as unresolved (0), not missing
        resolved.setdefault(str(i), False)
    return resolved


def load_harness_report(run_id: str, predictions_stem: str | None = None) -> dict[str, Any] | None:
    candidates = [
        Path(f"{predictions_stem}.{run_id}.json") if predictions_stem else None,
        Path(f"gold.{run_id}.json"),
        Path(f"{run_id}.json"),
    ]
    candidates.extend(Path(".").glob(f"*.{run_id}.json"))
    for rp in candidates:
        if rp is None or not rp.exists():
            continue
        try:
            return json.loads(rp.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
    return None
