# CommSCM — Decision Log

**Purpose:** Short audit trail of governance and scientific decisions (not a lab notebook for every commit).  
**Rule:** Log decisions that change protocol, claims, scope, or freeze boundaries. Implementation bugfixes in adapters need no entry unless they change what the paper claims.

| Date | Decision | Rationale | Artifacts |
|------|----------|-----------|-----------|
| 2026-08-01 | Freeze CommSCM core; validation-only phase | Stop building; start falsifying | `FREEZE.md`, `README.md` |
| 2026-08-01 | Claims ledger + falsification gate | Prevent overclaiming / silent core edits | `CLAIMS_LEDGER.md`, `FALSIFICATION_REPORT.md` |
| 2026-08-01 | Rename Part VI → Verified–**shaped** pilot; reserve VI.B official | Avoid misleading “SWE-bench” claims | `PART_VI_BENCHMARKS.md` |
| 2026-08-01 | Evidence ladder + revisit rule | No lower-level retuning without higher-level falsification | `FREEZE.md` |
| 2026-08-01 | Branch policy: `main` frozen; `investigation/*` exploratory | Audit trail for any future core change | `README.md`, `FREEZE.md` |
| 2026-08-01 | VI.B prereg H5; PASS = process integrity (no RAP floors) | Measure reality; avoid exam-style thresholds | `PART_VI_B_PREREGISTRATION.md` |
| 2026-08-01 | No new internal benches unless official gap | External credibility only | `FREEZE.md` advising rules |
| 2026-08-02 | Reproducibility artifact required for cited experiments | Reviewer-clean reproduction | `REPRODUCIBILITY.md` |
| 2026-08-02 | Weekly deliverable = experiment / falsification / paper section / repro improvement only | Discipline over feature expansion | `README.md`, `REPRODUCIBILITY.md` |
| 2026-08-02 | Nothing enters the paper unless in claims ledger; commits = science or reproducibility only | Prevent overclaiming / cleverness drift | `CLAIMS_LEDGER.md`, `FREEZE.md`, `README.md` |
| 2026-08-02 | **VI.B Experiment Frozen** — n=100, seed=42, gpt-4o-mini temp0, harness f7bbbb2… | Lock before writing/running; immutable without amendment | `PART_VI_B_PREREGISTRATION.md`, `results/part_vi_b_instance_list.json` |
| 2026-08-02 | Paper figures + empty result tables prepared pre-results | Avoid redesign during interpretation; raw→tables→CIs→ledger→prose | `paper/figures/`, `paper/tables/EMPTY_RESULTS.md` |
| 2026-08-02 | VI.B post-result decision paths locked (succeed / partial / clear fail) | Prevent post-hoc interpretive bias | `PART_VI_B_PREREGISTRATION.md` § Decision rule after VI.B |
| 2026-08-02 | Result-Blind Interpretation Rule (analysis/metrics frozen pre-open; post-hoc reruns labeled) | Prevent optimize-after-seeing-answers | `PART_VI_B_PREREGISTRATION.md` |
| 2026-08-02 | **Governance complete** — no further process docs; execute evidence | Diminishing returns on planning | — |
| 2026-08-02 | VI.B harness integrity fix: **one predictions file per method** + unlock `max_workers` (default 4) | SWE-bench collapses by `instance_id` (last wins); worker count not locked in prereg — free wall-clock, not a protocol change | `commscm/adapters/swebench/official_eval.py`, runner `--docker-only` / `--max-workers`; prior static-only Docker arms **non-primary** |
| 2026-08-02 | Cold-draft clear-fail falsification template before final VI.B numbers | Avoid writing fail branch after emotional stake in outcome | `commscm/falsification_reports/DRAFT_vi_b_clear_fail.md` |
| 2026-08-04 | **VI.B Partially succeeds** — process PASS; Resolve@1=0 all methods; do **not** falsify core; do **not** claim SWE-bench Resolve@1 win | Attribution/proxy hold (CR gold-edge 1.00); audited failures are patch apply (Case B/C); paper claim → localization + patch-synthesis bottleneck | `PART_VI_B_RESULTS.md`, `CLAIMS_LEDGER.md`, `part_vi_b_analysis.json`, `part_vi_b_patch_apply_audit.json` |
| 2026-08-04 | Freeze CommSCM core after VI.B null Resolve@1; no adapter “rescue” edits that reopen IF-C-SCM/CR/Replay/CCAS | Reviewer risk is overclaiming Resolve@1 or silently fixing synthesis; honest failure taxonomy motivates future work | `THREATS_TO_VALIDITY.md`, ledger H5 split |
| 2026-08-04 | Soften VI.B wording: Resolve@1 does **not directly falsify** attribution (failures at patch apply); paper pitch = attribution framework + transfer + synthesis bottleneck; oracle-patch = #1 remaining gap | Avoid dismissive “benchmark doesn’t matter”; keep Resolve@1 out of abstract/conclusion wins | `PART_VI_B_RESULTS.md`, `CLAIMS_LEDGER.md` |
| 2026-08-04 | **VI.B CLOSED** — never rerun for dislike of numbers; next = VI.C WebArena → hostile review → write; oracle-patch optional after VI.C; no new algorithms | Evidence > complexity; protect freeze | `STATUS_AFTER_PART_V.md`, `PART_VI_C_WEBARENA.md`, `FREEZE.md` |
| 2026-08-04 | Start VI.C: draft prereg (`PART_VI_C_PREREGISTRATION.md`); H6a localization vs H6b Success split; run denied until freeze signed | Same process integrity as VI.B; strengthen external evidence | `PART_VI_C_PREREGISTRATION.md` |
| 2026-08-04 | **VI.C Experiment Frozen** — Benchmark A (original WebArena), n=100, seed=42; validation-only; no method changes regardless of outcome | Literature-standard bench + stronger external n; protect freeze | `PART_VI_C_PREREGISTRATION.md`, `results/part_vi_c_instance_list.json` |
| 2026-08-04 | VI.C adapter scaffold + smoke PASS (task 743, CR hit gold C1); offline fixture; core untouched | Validation sequence: adapter → smoke → full run | `commscm/adapters/webarena/`, `results/part_vi_c_smoke.json` |
| 2026-08-04 | Lock smoke≠full-VI.C distinction; ledger: smoke = adapter check only; WebArena generalization remains Not tested | Prevent overclaim before official env | `PART_VI_C_WEBARENA.md`, `CLAIMS_LEDGER.md` |
| 2026-08-04 | VI.C official env **blocked**: ~304GB site images vs ~41GB free; no AWS; runner fails closed; shopping_admin download for wire-only | E6 capacity; do not fake Success | `WEBARENA_BRINGUP.md`, `part_vi_c_env_status.json`, `THREATS_TO_VALIDITY.md` |
| 2026-08-04 | **VI.C frozen as preregistered-not-executed** (infra); stop hardware chase; paper path = polish + submit; WebArena = limitation not falsification | Evidence you have is the contribution; reviewers can judge | `PART_VI_C_RESULTS.md`, `CLAIMS_LEDGER.md`, `STATUS_AFTER_PART_V.md` |
| 2026-08-04 | E6 diagnosed: Windows CRLF in SWE-bench `eval.sh` breaks Linux eval; gold patches OK under LF; n=100 oracle **blocked** until harness write fix + sample re-smoke | Not CommSCM; adapter/harness wrapper only | `E6_GOLD_FAIL_DIAGNOSIS.md`, `results/e6_diagnosis/` |
| 2026-08-04 | LF harness fix + samples: gold n=10 Resolve@1=**1.00**; CR-guided same IDs Resolve@1=**0.00** (10/10 apply errors). Full n=100 still held | CRLF fixed; VI.B CR null not lifted on this sample | `LF_FIX_SAMPLE_RESULTS.md`, `run_evaluation_lf.py` |

Append new rows at the bottom. Do not rewrite history; amend with a new dated row if a decision is reversed.
