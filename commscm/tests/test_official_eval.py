"""Tests for official SWE-bench eval helpers (adapter/harness — not core)."""

from __future__ import annotations

from pathlib import Path

from commscm.adapters.swebench.official_eval import (
    normalize_model_patch,
    resolve_map_from_report,
    write_predictions_jsonl,
)


def test_normalize_adds_ab_prefixes() -> None:
    raw = "--- django/foo.py\n+++ django/foo.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
    out = normalize_model_patch(raw)
    assert "--- a/django/foo.py" in out
    assert "+++ b/django/foo.py" in out


def test_normalize_strips_apply_patch_stub() -> None:
    raw = (
        "--- a/x.py\n+++ b/x.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
        "def apply_patch(path):\n    pass\n"
    )
    out = normalize_model_patch(raw)
    assert "def apply_patch" not in out
    assert "@@ -1,1 +1,1 @@" in out


def test_resolve_map_marks_errors_unresolved() -> None:
    report = {
        "resolved_ids": ["a"],
        "unresolved_ids": ["b"],
        "error_ids": ["c"],
    }
    m = resolve_map_from_report(report)
    assert m == {"a": True, "b": False, "c": False}


def test_write_predictions_normalizes(tmp_path: Path) -> None:
    path = tmp_path / "preds.jsonl"
    write_predictions_jsonl(
        [
            {
                "instance_id": "x",
                "model_name_or_path": "commscm-vi-b-cr_guided",
                "model_patch": "--- foo.py\n+++ foo.py\n@@ -1 +1 @@\n-a\n+b\n",
            }
        ],
        path,
        normalize=True,
    )
    text = path.read_text(encoding="utf-8")
    assert "a/foo.py" in text
