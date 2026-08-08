"""
Part VI continuous runner: Stage 2 → 3 → 4 (no interactive feedback).

Writes a master log under results/part_vi_overnight_log.txt
"""

from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "results" / "part_vi_overnight_log.txt"
STATUS = ROOT / "results" / "part_vi_overnight_status.json"


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_stage(name: str, argv: list[str]) -> int:
    log(f"START {name}: {' '.join(argv)}")
    t0 = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-m", *argv],
        cwd=str(ROOT),
        capture_output=False,
    )
    elapsed = round(time.perf_counter() - t0, 1)
    log(f"END {name} exit={proc.returncode} elapsed_s={elapsed}")
    return int(proc.returncode)


def main() -> None:
    LOG.write_text("", encoding="utf-8")
    log("Part VI overnight runner starting (Stages 2–4)")
    codes: dict[str, int] = {}

    codes["stage2"] = run_stage(
        "stage2",
        [
            "commscm.experiments.part_vi_stage2_swebench_attr",
            "--n-runs",
            "24",
            "--n-instances",
            "8",
            "--stability-reps",
            "3",
        ],
    )
    if codes["stage2"] != 0:
        log("Stage 2 failed — continuing to Stage 3/4 per falsification protocol (document limitations)")

    codes["stage3"] = run_stage(
        "stage3",
        [
            "commscm.experiments.part_vi_stage3_swebench_repair",
            "--n-runs",
            "18",
            "--n-instances",
            "6",
        ],
    )

    codes["stage4"] = run_stage(
        "stage4",
        [
            "commscm.experiments.part_vi_stage4_swebench_baselines",
            "--n-runs",
            "36",
            "--n-instances",
            "6",
        ],
    )

    import json

    STATUS.write_text(json.dumps({"exit_codes": codes, "done": True}, indent=2), encoding="utf-8")
    log(f"ALL DONE exit_codes={codes}")
    # Non-zero if any stage failed
    sys.exit(0 if all(c == 0 for c in codes.values()) else 1)


if __name__ == "__main__":
    main()
