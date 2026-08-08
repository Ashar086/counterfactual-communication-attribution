"""
Load WebArena task intents for Part VI.C.

Offline fixtures always available. Live configs load when
``WEBARENA_ROOT/config_files/{id}.json`` exists (after upstream
``scripts/generate_test_data.py``).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WebArenaInstance:
    task_id: str
    intent: str
    sites: tuple[str, ...] = ()
    raw: dict[str, Any] | None = None
    source: str = "offline_fixture"


_FIXTURE_INTENTS: dict[str, dict[str, Any]] = {
    "743": {
        "intent": (
            "Find the price of the cheapest wireless headphones on the shopping site "
            "and report the dollar amount."
        ),
        "sites": ["shopping"],
    },
    "419": {
        "intent": (
            "On the shopping admin site, check whether order #001 has status Complete."
        ),
        "sites": ["shopping_admin"],
    },
    "231": {
        "intent": (
            "Post a short comment on the Reddit site thanking the original poster "
            "in the most recent thread on the front page."
        ),
        "sites": ["reddit"],
    },
    "619": {
        "intent": (
            "On GitLab, open the README of the public project named 'a11y' and "
            "quote the first heading."
        ),
        "sites": ["gitlab"],
    },
    "614": {
        "intent": (
            "Using the map site, find driving directions from Carnegie Mellon University "
            "to Pittsburgh International Airport and report the estimated time."
        ),
        "sites": ["map"],
    },
}


def _webarena_root() -> Path | None:
    raw = os.environ.get("WEBARENA_ROOT", "").strip()
    if not raw:
        return None
    p = Path(raw)
    return p if p.is_dir() else None


def load_webarena_instance(task_id: str | int) -> WebArenaInstance:
    """
    Prefer live ``config_files/{id}.json`` under ``WEBARENA_ROOT``;
    else offline fixture; else a generic intent stub (still runnable).
    """
    tid = str(int(task_id)) if str(task_id).isdigit() else str(task_id)
    root = _webarena_root()
    if root is not None:
        cfg = root / "config_files" / f"{tid}.json"
        if cfg.is_file():
            data = json.loads(cfg.read_text(encoding="utf-8"))
            intent = str(
                data.get("intent")
                or data.get("instruction")
                or data.get("task")
                or ""
            ).strip()
            sites = data.get("sites") or data.get("require_login") or []
            if isinstance(sites, str):
                sites = [sites]
            if not intent:
                intent = f"WebArena task {tid}"
            return WebArenaInstance(
                task_id=tid,
                intent=intent,
                sites=tuple(str(s) for s in sites),
                raw=data,
                source=f"webarena_root:{cfg}",
            )

    fix = _FIXTURE_INTENTS.get(tid)
    if fix:
        return WebArenaInstance(
            task_id=tid,
            intent=str(fix["intent"]),
            sites=tuple(fix.get("sites") or ()),
            raw=dict(fix),
            source="offline_fixture",
        )

    return WebArenaInstance(
        task_id=tid,
        intent=(
            f"Complete WebArena task {tid} using the available websites. "
            "Produce concrete navigation actions."
        ),
        sites=(),
        raw=None,
        source="generic_stub",
    )


def load_vi_c_instance_list(path: str | Path | None = None) -> list[int]:
    p = Path(path or "results/part_vi_c_instance_list.json")
    data = json.loads(p.read_text(encoding="utf-8"))
    return [int(x) for x in data["task_ids"]]
