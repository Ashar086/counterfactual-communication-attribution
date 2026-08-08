# Part VI.B — Official SWE-bench Verified Results

**Status:** ✅ **CLOSED** (2026-08-04). Process PASS / partially succeeds.  
**Do not rerun or reinterpret to chase Resolve@1.** Touch only for a confirmed reproducibility bug.  
**Preregistration:** [`PART_VI_B_PREREGISTRATION.md`](PART_VI_B_PREREGISTRATION.md) (Experiment Frozen 2026-08-02).  
**Analysis:** `results/part_vi_b_analysis.json` (frozen bootstrap plan).  
**Patch-apply audit:** `results/part_vi_b_patch_apply_audit.json` (n=20, seed 42).

**Core CommSCM:** unchanged. No falsification report filed for IF-C-SCM / CR / Replay / CCAS.

**Next evidence:** Part VI.C WebArena (`PART_VI_C_WEBARENA.md`) — adapter only.

---

## Run metadata

| Field | Value |
|-------|--------|
| Experiment Frozen date | **2026-08-02** |
| n | **100** (seed 42) · `results/part_vi_b_instance_list.json` |
| Model / API | `gpt-4o-mini` · temp 0.0 · top_p 1.0 · max_tokens 4096 |
| Docker / harness | `SWE-bench/SWE-bench@f7bbbb2…` · namespace `swebench` · per-method predictions (last-wins fix) |
| Primary artifacts | `results/part_vi_b_official.json` · `results/part_vi_b_analysis.json` |
| Harness reports | `commscm-vi-b-{method}.vi_b_rescore_part_vi_b_official_{method}.json` |

---

## Primary results — Resolve@1 (95% bootstrap CIs)

| Method | Resolve@1 mean [95% CI] | Gold Edge Hit [95% CI] | Proxy pass (y≥0.5) | RAP (gold among edits) |
|--------|-------------------------|------------------------|--------------------:|------------------------|
| CR-guided | **0.00** [0.00, 0.00] | **1.00** [1.00, 1.00] | 0.97 | 1.00 |
| Reward-only | **0.00** [0.00, 0.00] | 0.33 [0.24, 0.42] | 0.33 | 0.33 |
| Random | **0.00** [0.00, 0.00] | 0.59 [0.49, 0.69] | 0.40 | 0.59 |
| Static heuristic | **0.00** [0.00, 0.00] | 0.67 [0.58, 0.76] | 0.53 | 0.67 |

**Effect size (CR − reward-only Resolve@1):** mean diff **0.00** · Cohen’s dz **0.00** · n_paired=100.

### Official harness outcome mix (n=100 where available)

| Method | Resolved | Unresolved (apply OK, tests fail) | Errors (mostly patch-apply) |
|--------|----------:|----------------------------------:|----------------------------:|
| CR-guided* | 0 | 2† | majority apply-errors + resume batch 4 |
| Reward-only | 0 | 20 | 80 |
| Random | 0 | 16 | 84 |
| Static | 0 | 1 | 99 |

\*CR aggregate JSON after resume reflects the 6-instance catch-up file; full-pass logs show the same pattern (0 resolves, dominate apply-errors).  
†Plus earlier django unresolved reports retained on disk from prior partial runs.

---

## Failure-mode pipeline (science vs engineering)

```text
Trace → CommSCM Attribution → Communication edit → Patch synthesis → git apply → Resolve@1
         ✅ gold-edge / proxy              ❌ dominant failure (Case B/C)
```

| Stage | Evidence | Verdict |
|-------|----------|---------|
| Attribution (CR) | Gold-edge hit 1.00 vs reward-only 0.33; p@1=1.00 | Holds under poison construct |
| Communication edit | Proxy repair ~0.97 for CR | Sensible soft intervention |
| Patch synthesis / `git apply` | Audit 20/20 failures still gold+proxy; categories: wrong path 7, invalid diff 7, hunk mismatch 6 | **Primary bottleneck** |
| Semantic Resolve@1 | 0/100 all methods | No end-to-end SWE-bench win |

**Interpretation (careful):** Official Resolve@1 does **not directly falsify** the attribution mechanism, because the dominant observed failures occurred during **downstream patch application** rather than communication localization (Case A not supported by the audit).  
**Unsupported claim:** CommSCM improves official Resolve@1 — contradicted by 0.00 for all methods.

**Largest remaining empirical gap:** No **oracle-patch control** (correct CommSCM edge → oracle/strong synthesizer → Resolve@1). Without it, usefulness of the repair *decision* for end-to-end repair is supported only indirectly (gold-edge + proxy), not by definitive causal separation from patch synthesis.

---

## Process PASS checklist

- [x] P0 Core unchanged  
- [x] P1 ≥95% pipeline execution (pipeline_ok_rate=1.00)  
- [x] P2 CIs + effect sizes reported (`part_vi_b_analysis.json`)  
- [x] P3 Transparent baseline comparison  
- [x] P4 Honest write-up + ledger update  

---

## Expected failure modes observed

| ID | Observed? | Notes |
|----|-----------|-------|
| E5 | **Yes** | Resolve@1 null for all methods (vs shaped pilot) |
| E6 | Partial | Early DNS/Docker stalls; mitigated; not primary final mode |
| E7 | **Yes** | Gold-edge / proxy success ≫ Resolve@1 (construct gap) |
| Patch synthesis | **Yes** | Dominant Docker “error” class |

---

## Verdict (prereg decision path)

| Outcome | |
|---------|--|
| Process PASS / FAIL | **PASS** |
| Decision path | **Partially succeeds** |
| Scientific interpretation | Attribution localizes injected harm under the official adapter construct; Resolve@1 is blocked at patch synthesis/applicability in the audited sample. Null Resolve@1 is a **limitation**, not automatic core falsification — and not proof that repair decisions are end-to-end useful without an oracle-patch control. |
| Falsification report (core) | **No** — limitation; do not reopen IF-C-SCM/CR/Replay/CCAS |

**Paper positioning (locked):**  
Not “We outperform SWE-bench” / “CommSCM improves Resolve@1.”  

Yes: *We introduce a communication-centric causal attribution framework for multi-agent systems, demonstrate efficient counterfactual replay and adapter-level transfer across frameworks, and show that official software-engineering evaluation exposes downstream patch synthesis—not communication attribution—as the dominant bottleneck for end-to-end repair.*

---

## Ledger updates

See `CLAIMS_LEDGER.md`: official Resolve@1 improvement → **Unsupported**; localization under VI.B poison construct → **Supported** (scoped); SOTA / abstract Resolve@1 → still ❌.
