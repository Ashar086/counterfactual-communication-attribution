# LF-fixed harness sample results (factual)

**Date:** 2026-08-04  
**Fix:** `eval.sh` / shell writes forced to Unix LF via  
`commscm/adapters/swebench/run_evaluation_lf.py` + `official_eval.py`  
(+ local SWE-bench-src `write_text(..., newline="\n")`).  
**CommSCM core:** unchanged. Full n=100 **not** run.

Same 10 instance IDs (`sample_seed=7` from locked VI.B list).

---

## 1. Gold-patch sample (LF-fixed)

**Artifact:** `results/oracle_gold_patch_sample_lf.json`  
**Run ID:** `oracle_gold_sample_n10_s7_lf`

| Metric | Before (CRLF) | After (LF) |
|--------|---------------|------------|
| Resolved | 0/10 | **10/10** |
| Resolve@1 mean | 0.00 | **1.00** |
| Errors | 0 | 0 |

**Conclusion:** Harness fix works. Dataset gold patches resolve on this host when `eval.sh` is LF.

---

## 2. CR-guided VI.B synthesized patches (LF-fixed)

**Artifact:** `results/cr_guided_sample_n10_s7_lf.json`  
**Run ID:** `cr_guided_sample_n10_s7_lf`  
**Patches:** taken from `results/part_vi_b_official.json` (`method=cr_guided`), same IDs.

| Metric | Value |
|--------|-------|
| Resolved | **0/10** |
| Unresolved | 0 |
| Errors | **10/10** |
| Resolve@1 mean | **0.00** |

Failure mode (logs): **patch apply failure** (`APPLY_PATCH_FAIL` / no `report.json` grading), not CRLF / not “tests ran and failed.”

All 10 still had `hit_gold_edge=true` in the original VI.B rows.

---

## 3. Implications (factual)

| Question | Sample answer |
|----------|----------------|
| Is gold Resolve@1 systematically 0 after LF fix? | **No** — 10/10 resolved |
| Is CR-guided Resolve@1 still 0 after LF fix? | **Yes** — 0/10 resolved (apply errors) |
| Was original VI.B CR Resolve@1=0.00 *only* CRLF corruption? | **Not for this sample** — synthesized patches still do not apply under fixed harness |
| Redo full VI.B n=100 before trusting numbers? | Sample does **not** show CR Resolve@1 lifting above 0; full redo not indicated by this sample alone for “hidden resolves.” (Original error-vs-unresolved mix may still be partly mis-labeled where patches *did* apply under CRLF.) |

**Full n=100 oracle-patch:** still on hold pending your go-ahead.
