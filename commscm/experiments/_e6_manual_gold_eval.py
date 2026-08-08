"""Manual E6 diagnosis: run gold patch with LF-normalized eval.sh inside instance image."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

import docker


def put_file(container, dest: str, data: bytes) -> None:
    buf = io.BytesIO()
    name = Path(dest).name
    parent = str(Path(dest).as_posix().rsplit("/", 1)[0] or "/")
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo(name=name)
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    buf.seek(0)
    ok = container.put_archive(parent, buf.read())
    if not ok:
        raise RuntimeError(f"put_archive failed for {dest}")


def run_one(iid: str, image: str) -> Path:
    log_dir = Path(
        f"logs/run_evaluation/oracle_gold_sample_n10_s7/commscm-oracle-gold/{iid}"
    )
    out_dir = Path("results/e6_diagnosis")
    out_dir.mkdir(parents=True, exist_ok=True)

    patch = log_dir.joinpath("patch.diff").read_text(encoding="utf-8").replace("\r\n", "\n")
    eval_lf = (
        log_dir.joinpath("eval.sh").read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    )
    out_dir.joinpath(f"{iid}_eval_lf.sh").write_bytes(eval_lf)

    client = docker.from_env()
    name = f"e6diag-{iid.replace('__', '-')}"
    try:
        client.containers.get(name).remove(force=True)
    except Exception:
        pass

    container = client.containers.run(
        image, command="sleep 7200", name=name, detach=True, working_dir="/testbed"
    )
    try:
        put_file(container, "/tmp/gold.patch", patch.encode())
        put_file(container, "/eval_lf.sh", eval_lf)

        apply = container.exec_run(
            ["bash", "-lc", "cd /testbed && git apply -v /tmp/gold.patch; echo EXIT:$?"],
        )
        apply_out = apply.output.decode("utf-8", "replace")
        out_dir.joinpath(f"{iid}_manual_apply.txt").write_text(apply_out, encoding="utf-8")

        ev = container.exec_run(
            ["bash", "-lc", "chmod +x /eval_lf.sh && /bin/bash /eval_lf.sh"],
            workdir="/testbed",
        )
        test_out = ev.output.decode("utf-8", "replace")
        out_path = out_dir / f"{iid}_manual_lf_test_output.txt"
        out_path.write_text(test_out, encoding="utf-8")
        meta = {
            "instance_id": iid,
            "image": image,
            "apply_exit": apply.exit_code,
            "eval_exit": ev.exit_code,
            "has_crlf_artifact_in_original_eval": b"\r\n"
            in log_dir.joinpath("eval.sh").read_bytes(),
            "manual_output": str(out_path),
            "contains_ModuleNotFoundError": "ModuleNotFoundError" in test_out,
            "contains_pipefail_cr": "pipefail\r" in test_out or "pipefail\r" in apply_out,
            "ok_lines": [ln for ln in test_out.splitlines() if " ok" in ln.lower()][-20:],
            "fail_lines": [ln for ln in test_out.splitlines() if "FAIL" in ln or "ERROR" in ln][
                :40
            ],
        }
        out_dir.joinpath(f"{iid}_manual_meta.json").write_text(
            __import__("json").dumps(meta, indent=2), encoding="utf-8"
        )
        print(__import__("json").dumps(meta, indent=2))
        return out_path
    finally:
        container.stop(timeout=15)
        container.remove(force=True)


if __name__ == "__main__":
    import sys

    iid = sys.argv[1] if len(sys.argv) > 1 else "django__django-11239"
    image = (
        sys.argv[2]
        if len(sys.argv) > 2
        else "swebench/sweb.eval.x86_64.django_1776_django-11239:latest"
    )
    run_one(iid, image)
