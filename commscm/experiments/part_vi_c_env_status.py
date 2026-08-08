"""Assess WebArena official env readiness; write results/part_vi_c_env_status.json."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from commscm.adapters.webarena.official_env import assess_environment, capacity_report


def main() -> None:
    status = assess_environment()
    out = {
        "env": asdict(status),
        "capacity": capacity_report(),
        "note": (
            "ready_for_official=false blocks part_vi_c_official_runner from claiming "
            "WebArena Success. Smoke fixtures are not official."
        ),
    }
    path = Path("results/part_vi_c_env_status.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    print(f"Wrote {path}")
    if not status.ready_for_official:
        raise SystemExit(f"ENV_NOT_READY: {status.blockage}")


if __name__ == "__main__":
    main()
