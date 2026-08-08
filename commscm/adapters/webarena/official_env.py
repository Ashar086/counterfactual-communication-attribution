"""
Official WebArena environment helpers (Part VI.C).

Does not modify CommSCM core. Fails closed: never invent official Success
without a live evaluator call against a configured environment.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_ENV_VARS = (
    "SHOPPING",
    "SHOPPING_ADMIN",
    "REDDIT",
    "GITLAB",
    "MAP",
    "WIKIPEDIA",
    "HOMEPAGE",
)

# Compressed image sizes from metis.lti.cs.cmu.edu (bytes) — for capacity planning
IMAGE_BYTES = {
    "shopping_final_0712.tar": 67_575_898_112,
    "shopping_admin_final_0719.tar": 9_640_032_256,
    "postmill-populated-exposed-withimg.tar": 53_435_097_088,
    "gitlab-populated-final-port8023.tar": 77_755_595_776,
    "wikipedia_en_all_maxi_2022-05.zim": 95_199_730_590,
}


@dataclass
class EnvStatus:
    webarena_root: str | None
    env_vars_set: bool
    missing_vars: list[str]
    reachable: dict[str, bool | str]
    configs_generated: bool
    ready_for_official: bool
    blockage: str | None


def webarena_root() -> Path | None:
    raw = os.environ.get("WEBARENA_ROOT", "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_dir() else None
    default = Path(r"D:\WebArena\webarena")
    return default if default.is_dir() else None


def missing_env_vars() -> list[str]:
    return [k for k in REQUIRED_ENV_VARS if not os.environ.get(k, "").strip()]


def _probe(url: str, timeout: float = 5.0) -> bool | str:
    if not url or url.upper() == "PASS":
        return "skipped"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= getattr(resp, "status", 200) < 500
    except Exception as exc:  # noqa: BLE001
        return f"error:{type(exc).__name__}"


def probe_sites() -> dict[str, bool | str]:
    out: dict[str, bool | str] = {}
    for key in REQUIRED_ENV_VARS:
        out[key] = _probe(os.environ.get(key, ""))
    return out


def generate_configs(root: Path | None = None) -> Path:
    """Run the same substitution as upstream ``scripts/generate_test_data.py``."""
    root = root or webarena_root()
    if root is None:
        raise FileNotFoundError("WEBARENA_ROOT not set / D:\\WebArena\\webarena missing")
    missing = missing_env_vars()
    if missing:
        raise RuntimeError(f"Missing env vars for config generation: {missing}")

    raw_path = root / "config_files" / "test.raw.json"
    raw = raw_path.read_text(encoding="utf-8")
    repl = {
        "__GITLAB__": os.environ["GITLAB"],
        "__REDDIT__": os.environ["REDDIT"],
        "__SHOPPING__": os.environ["SHOPPING"],
        "__SHOPPING_ADMIN__": os.environ["SHOPPING_ADMIN"],
        "__WIKIPEDIA__": os.environ["WIKIPEDIA"],
        "__MAP__": os.environ["MAP"],
    }
    for k, v in repl.items():
        raw = raw.replace(k, v)
    test_json = root / "config_files" / "test.json"
    test_json.write_text(raw, encoding="utf-8")
    data = json.loads(raw)
    for idx, item in enumerate(data):
        (root / "config_files" / f"{idx}.json").write_text(
            json.dumps(item, indent=2), encoding="utf-8"
        )
    return test_json


def assess_environment() -> EnvStatus:
    root = webarena_root()
    missing = missing_env_vars()
    reachable = probe_sites() if not missing else {}
    configs = False
    if root is not None:
        configs = (root / "config_files" / "0.json").is_file()
    # Official ready: all vars set, configs exist, and no hard probe failures
    # (HOMEPAGE may be PASS; unreachable sites block readiness)
    hard_fail = [
        k
        for k, v in reachable.items()
        if k != "HOMEPAGE" and v is not True and v != "skipped"
    ]
    blockage = None
    if root is None:
        blockage = "webarena_repo_missing"
    elif missing:
        blockage = f"env_vars_missing:{','.join(missing)}"
    elif hard_fail:
        blockage = f"sites_unreachable:{','.join(hard_fail)}"
    elif not configs:
        blockage = "configs_not_generated"

    ready = blockage is None
    return EnvStatus(
        webarena_root=str(root) if root else None,
        env_vars_set=not missing,
        missing_vars=missing,
        reachable=reachable,
        configs_generated=configs,
        ready_for_official=ready,
        blockage=blockage,
    )


def capacity_report() -> dict[str, Any]:
    total = sum(IMAGE_BYTES.values())
    return {
        "images_bytes": dict(IMAGE_BYTES),
        "images_gb_approx": {k: round(v / 1e9, 1) for k, v in IMAGE_BYTES.items()},
        "total_compressed_gb_approx": round(total / 1e9, 1),
        "recommendation": (
            "Use AWS AMI ami-08a862bf98e3bd7aa (us-east-2) per upstream README, "
            "or attach ≥400GB free disk before local docker load of all sites."
        ),
    }
