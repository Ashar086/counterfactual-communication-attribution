# E6 Diagnosis — Why gold patches fail FAIL_TO_PASS on this host

**Date:** 2026-08-04  
**Instances:** `django__django-11239`, `sympy__sympy-17655` (from oracle gold sample)  
**Scope:** Harness/environment only. CommSCM/CCAS/CR untouched. Full n=100 oracle run **not** started.

---

## Verdict

**Root cause: Windows CRLF line endings in `eval.sh`.**

On this Windows host, SWE-bench harness writes `eval.sh` via `Path.write_text(...)` which defaults to `\r\n`. That script is copied into a Linux container and executed with `/bin/bash /eval.sh`. Every command then sees a trailing `\r`, so conda/pip/cd fail and **tests never actually run**. The grader then marks all FAIL_TO_PASS (and PASS_TO_PASS) as failures.

This is **not**:
- a gold-patch quality problem
- a FAIL_TO_PASS ID mismatch
- a harness commit / dataset version mismatch (for these two cases)

---

## Checks requested

### (a) Test environment builds

Prebuilt images `swebench/sweb.eval.x86_64.*:latest` pull and start successfully. No image build failure.

### (b) FAIL_TO_PASS / PASS_TO_PASS IDs

Match HuggingFace `princeton-nlp/SWE-bench_Verified` exactly for both instances.

| Instance | Dataset FAIL_TO_PASS | Report failure list |
|----------|----------------------|---------------------|
| django-11239 | `test_ssl_certificate (dbshell.test_postgresql…)` | same |
| sympy-17655 | `test_point`, `test_point3D` | same |

### (c) Harness / commit

- Installed swebench: **4.1.0** @ **`f7bbbb2ccdf479001d6467c9e34af59e44a840f9`** (matches VI.B prereg)
- Dataset: `princeton-nlp/SWE-bench_Verified` (same as VI.B)

### (d) Manual gold + tests outside automated pipeline

| Condition | django-11239 | sympy-17655 |
|-----------|--------------|-------------|
| Automated sample (`eval.sh` CRLF) | apply OK; tests broken; Resolve=0 | same |
| Manual (`eval.sh` converted to LF) | **all listed tests `ok`**, eval_exit=0 | **all listed tests `ok`**, eval_exit=0 |

Artifacts:
- `results/e6_diagnosis/django__django-11239_manual_lf_test_output.txt`
- `results/e6_diagnosis/sympy__sympy-17655_manual_lf_test_output.txt`
- `results/e6_diagnosis/*_manual_meta.json`
- Helper: `commscm/experiments/_e6_manual_gold_eval.py`

---

## Exact errors from automated (CRLF) run

### django__django-11239 (`test_output.txt`)

```text
/eval.sh: line 2: set: pipefail\r: invalid option name
+ source $'/opt/miniconda3/bin/activate\r'
/eval.sh: line 3: /opt/miniconda3/bin/activate\r: No such file or directory
+ conda activate $'testbed\r'
CondaError: Run 'conda init' before 'conda activate'
+ cd $'/testbed\r'
/eval.sh: line 5: cd: $'/testbed\r': No such file or directory
...
+ python -m pip install -e $'.\r'
ERROR: . is not a valid editable requirement.
...
ModuleNotFoundError: No module named 'django'
RuntimeError: Django module not found, reference tests/README.rst for instructions.
```

`eval.sh` on disk: **106 CR + 106 LF** (`b'#!/bin/bash\r\nset -uxo pipefail\r\n...'`).

### sympy__sympy-17655 (`test_output.txt`)

```text
/eval.sh: line 2: set: pipefail\r: invalid option name
+ source $'/opt/miniconda3/bin/activate\r'
...
CondaError: Run 'conda init' before 'conda activate'
+ python -m pip install -e $'.\r'
ERROR: . is not a valid editable requirement.
...
ModuleNotFoundError: No module named 'mpmath'
ImportError: SymPy now depends on mpmath as an external library.
```

### Why `patch_successfully_applied: true` was misleading

Model gold patch was applied (via `patch` after `git apply` failed on test files with CR issues). The **code** change landed, but **eval never ran** because of CRLF in `eval.sh`. Grading therefore reported FAIL_TO_PASS failures without real unittest results.

---

## Code locus (upstream harness)

`swebench/harness/run_evaluation.py` (~line 198–199):

```python
eval_file = Path(log_dir / "eval.sh")
eval_file.write_text(test_spec.eval_script)  # Windows → CRLF
```

Note: Dockerfiles already strip `\r` from `setup_env.sh` / `setup_repo.sh`, but **not** from runtime `eval.sh`.

---

## Fix options (not applied yet)

1. **Adapter/harness wrapper (preferred for this repo):** when writing `eval.sh`, force `newline='\n'` (or strip `\r` before copy). Does **not** change CommSCM core.
2. Upstream SWE-bench patch: same `newline='\n'` in `write_text`.
3. Re-run oracle gold sample / VI.B Docker arms only after the wrapper fix.

---

## Implication for oracle-patch control

The n=10 gold Resolve@1 = 0.00 baseline is **invalid as a measure of patch quality** on this host until CRLF is fixed. After fix, re-run the **same n=10 sample** before considering n=100.
