"""
Windows LF fix for SWE-bench harness (adapter/harness wrapper — not CommSCM core).

Problem: on Windows, ``Path.write_text`` writes CRLF into ``eval.sh``. Linux bash
then sees ``pipefail\\r`` / ``activate\\r`` and tests never run (E6).

This module monkeypatches ``Path.write_text`` so ``*.sh`` (and common patch
files written next to eval) use ``newline='\\n'``, then delegates to the
upstream ``swebench.harness.run_evaluation`` CLI.
"""

from __future__ import annotations

import pathlib
import runpy
import sys


_ORIG_WRITE_TEXT = pathlib.Path.write_text


def _lf_write_text(self: pathlib.Path, data, encoding=None, errors=None, newline=None):
    # Force Unix newlines for shell scripts copied into Linux containers.
    if isinstance(data, str) and self.suffix == ".sh" and newline is None:
        newline = "\n"
    # Predictions / intermediate patches: also prefer LF for git apply in Linux.
    if isinstance(data, str) and self.name in {"patch.diff", "eval.sh"} and newline is None:
        newline = "\n"
    return _ORIG_WRITE_TEXT(
        self, data, encoding=encoding, errors=errors, newline=newline
    )


def apply_lf_patch() -> None:
    pathlib.Path.write_text = _lf_write_text  # type: ignore[method-assign]


def main(argv: list[str] | None = None) -> None:
    apply_lf_patch()
    # Re-exec upstream module as __main__ with remaining argv.
    if argv is not None:
        sys.argv = [sys.argv[0], *argv]
    else:
        # When invoked as ``python -m commscm.adapters.swebench.run_evaluation_lf``,
        # strip our module name and prepend upstream-compatible argv[0].
        sys.argv = ["swebench.harness.run_evaluation", *sys.argv[1:]]
    runpy.run_module("swebench.harness.run_evaluation", run_name="__main__")


if __name__ == "__main__":
    main()
