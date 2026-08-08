# Threats to Validity

**Purpose:** Living log of where frozen CommSCM may fail to generalize.  
**Rule:** Write it down **before** fixing. Core CommSCM patches are findings, not silent product work.

**Mindset:** Falsify CommSCM — *Under what conditions does the frozen method stop working?*

Headings below map to what NeurIPS reviewers look for.

---

## How to log an issue

| Field | Content |
|-------|---------|
| Date | When observed |
| Setting | LangGraph / AutoGen / SWE-bench / WebArena / … |
| Section | Internal / Construct / External / Statistical |
| Symptom | extract / attribution / edit / re-run / metrics |
| Hypothesis | Why |
| CommSCM changed? | **No** (preferred) / Yes + justification |
| Status | open / mitigated-in-adapter / accepted-limitation |

---

## 1. Internal Validity

Threats from bugs and implementation error (not true method failure).

Checklist:
- [x] Parser / extractor bugs
- [x] Adapter bugs (wrong edge gate, sticky mechanisms)
- [x] Implementation errors in harness / metrics / schedule confounding

### Log

| Field | Content |
|-------|---------|
| Date | 2026-07-31 |
| Setting | SWE-bench Verified–shaped (Part VI Stage 4 harness) |
| Section | Internal / Construct |
| Symptom | Early Stage 4: reward_only “repaired” via `prune C4→C5` falling back to **dataset gold_patch** (oracle leak) |
| Hypothesis | Adapter prune_fallback must not be SWE-bench gold; terminal sink should stay attached per RESEARCH_LOG |
| CommSCM changed? | **No** — adapter: non-gold clean baseline; harness: skip C4→C5 edits |
| Status | mitigated-in-adapter |

| Field | Content |
|-------|---------|
| Date | 2026-08-02 |
| Setting | Part VI.B Docker batches 1–15 |
| Section | Internal / Statistical |
| Symptom | Resolve@1 missing in checkpoint; harness reports only `static_heuristic`; 14/15 errors |
| Hypothesis | `run_evaluation` collapses preds by `instance_id` (last wins). Not a CommSCM core failure — measurement bug |
| CommSCM changed? | **No** — harness wiring: per-method jsonl + `max_workers` parallelism (unlocked in prereg) |
| Status | mitigated-in-adapter (runner fix); prior Docker arm results non-primary |

---

## 2. Construct Validity

Does `RunTrace` faithfully represent the framework’s communication?

Checklist:
- [ ] Missing or mis-typed channels
- [ ] Message-passing not visible in API traces
- [ ] Agent↔agent vs exogenous edges ambiguous
- [ ] Tool calls / shared state not captured as events
- [ ] Same-task LangGraph vs AutoGen CR rankings disagree for structural (not stochastic) reasons

### Log
*(none yet)*

---

## 3. External Validity

Limits on environments and tasks studied.

Checklist:
- [ ] Only one framework (mitigated by Part V AutoGen; still not CrewAI / …)
- [ ] Only controlled poison suites (not organic failures)
- [x] Only SWE-style tasks / only WebArena (Part VI shaped + VI.B official done; VI.C WebArena pending)
- [ ] Long-horizon traces untested
- [ ] Non-deterministic tool outputs dominate outcomes

### Log

| Field | Content |
|-------|---------|
| Date | 2026-08-02 |
| Setting | Part VI.B gold Docker smoke (`django__django-14672`) |
| Section | External / Construct |
| Symptom | Official harness completed; gold patch applied; FAIL_TO_PASS still failed → resolved=0 |
| Hypothesis | E6 harness/environment constraint (image/parser/platform) may dominate Resolve@1 independently of CommSCM |
| CommSCM changed? | **No** |
| Status | open — log before interpreting VI.B Resolve@1; gold baseline not 100% on this host |

| Field | Content |
|-------|---------|
| Date | 2026-08-04 |
| Setting | Part VI.B / oracle-gold sample on Windows host |
| Section | Internal / External (harness) |
| Symptom | Gold patches apply but FAIL_TO_PASS all fail; Resolve@1=0 even for dataset gold (n=10 sample) |
| Hypothesis | **E6 root cause found:** `eval.sh` written with Windows CRLF (`Path.write_text`); Linux container bash sees `pipefail\r`, conda/pip fail, tests never run. Manual LF-normalized `eval.sh` → django-11239 and sympy-17655 gold tests all `ok`. See `E6_GOLD_FAIL_DIAGNOSIS.md` |
| CommSCM changed? | **No** |
| Status | open — fix harness wrapper (`newline='\n'` for eval.sh); re-smoke n=10 gold before any n=100 |

| Field | Content |
|-------|---------|
| Date | 2026-08-04 |
| Setting | Part VI.B official Verified n=100 × 4 methods |
| Section | External / Construct |
| Symptom | Resolve@1 = 0.00 all methods; harness errors ≫ unresolved; CR gold-edge hit 1.00 and proxy≈0.97 |
| Hypothesis | **E5 + E7**: end-to-end Resolve@1 is dominated by **downstream patch synthesis / `git apply`** (wrong paths, malformed diffs, hunk mismatch), not by wrong communication-edge selection. Pipeline: Trace → CommSCM Attribution → edit decision → **Patch synthesis (adapter)** → git apply → Resolve@1. Audit n=20 apply-failures: 20/20 still hit_gold_edge + proxy pass → Case B/C, not Case A |
| CommSCM changed? | **No** — accepted as limitation; do not claim Resolve@1 improvement; do not reopen core |
| Status | accepted-limitation — paper: localization Supported; H5 end-to-end Unsupported; motivate better patch synthesis as future work |

| Field | Content |
|-------|---------|
| Date | 2026-08-04 |
| Setting | Part VI.B / SWE-bench adapter |
| Section | Construct |
| Symptom | Reviewer may treat malformed patches as “CommSCM failed” |
| Hypothesis | Patch synthesis is **adapter/LLM post-attribution**, not IF-C-SCM/CR/Replay/CCAS. Independence is architectural (module boundary) + empirical (correct edge + bad patch co-occur). **Largest remaining gap:** no oracle-patch control (CR edge → oracle patch → Resolve@1). Without it, “repair decision is useful end-to-end” rests on indirect evidence (gold-edge, proxy) only |
| CommSCM changed? | **No** |
| Status | accepted-limitation / open future experiment — elevate in Limitations; do not claim causal separation from synthesis until control exists |

| Field | Content |
|-------|---------|
| Date | 2026-08-04 |
| Setting | Part VI.C official WebArena bring-up (local Windows host) |
| Section | External |
| Symptom | Cannot load full official site stack locally |
| Hypothesis | **E6**: compressed images ≈283 GB (shopping 63 + admin 9 + forum 50 + gitlab 72 + wiki 89) vs ~41 GB free on C:/D:. No AWS CLI/credentials for recommended AMI `ami-08a862bf98e3bd7aa`. Locked n=100 needs all site classes. |
| CommSCM changed? | **No** |
| Status | accepted-limitation — preregistered-not-executed; paper states infra gap; protocol frozen for future run (`PART_VI_C_RESULTS.md`) |

---

## 4. Statistical Validity

Threats from sample size, noise, and overclaiming.

Checklist:
- [ ] Insufficient number of runs
- [ ] LLM stochasticity not measured
- [ ] No confidence intervals / significance where claimed
- [ ] Confounded schedules (method × fault locked)
- [ ] Absolute rates (e.g. 1.00) over-interpreted beyond controlled suite

### Log

| Field | Content |
|-------|---------|
| Date | 2026-08-01 |
| Setting | Part V repair n≈9; Part VI shaped repair n≈6–14 per method |
| Section | Statistical |
| Symptom | Absolute rates near 1.00 across stages; small pilot n |
| Hypothesis | Suites may be too easy / too aligned with poison→gold-edge design; rates are gate-passing pilots, not broad superiority |
| CommSCM changed? | **No** |
| Status | accepted-limitation — paper must use progression narrative + CIs at larger scale (Part VI.B) |

---

## Paper use

These four sections draft **Threats to Validity / Limitations**. Prefer honest boundary conditions over post-hoc core patches.

Related: `PART_V_FRAMEWORK_INVARIANCE.md` (H4, same-task cross-framework test).
