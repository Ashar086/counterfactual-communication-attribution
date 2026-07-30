"""Trace JSON/JSONL read/write and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from commscm.schema.events import RunTrace


def trace_to_dict(trace: RunTrace) -> dict:
    return trace.model_dump(mode="json")


def trace_from_dict(data: dict) -> RunTrace:
    return RunTrace.model_validate(data)


def write_trace_json(trace: RunTrace, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(trace_to_dict(trace), indent=2), encoding="utf-8")


def read_trace_json(path: str | Path) -> RunTrace:
    return trace_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def write_jsonl(traces: Iterable[RunTrace], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for tr in traces:
            fh.write(json.dumps(trace_to_dict(tr)) + "\n")


def read_jsonl(path: str | Path) -> list[RunTrace]:
    rows: list[RunTrace] = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(trace_from_dict(json.loads(line)))
    return rows
