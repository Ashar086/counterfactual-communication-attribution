# Oracle gold-patch sample baseline (factual)

**Date:** 2026-08-04  
**Artifact:** `results/oracle_gold_patch_sample.json`  
**Framing:** dataset `patch` → `model_patch`; same locked VI.B ID pool; not CR-locus-tied.  
**Sample:** n=10 from locked 100, `sample_seed=7`, `max_workers=2`  
**Wall time:** ~2.2 h (`elapsed_s=7780.7`)

## Aggregate

| Metric | Value |
|--------|-------|
| Resolved | **0 / 10** |
| Unresolved | **10 / 10** |
| Errors | 0 |
| Resolve@1 mean | **0.00** |

## Per instance

| Instance | Status | Resolve@1 |
|----------|--------|-----------|
| django__django-11239 | unresolved | 0 |
| sympy__sympy-17655 | unresolved | 0 |
| django__django-14434 | unresolved | 0 |
| sphinx-doc__sphinx-7910 | unresolved | 0 |
| django__django-15987 | unresolved | 0 |
| astropy__astropy-13977 | unresolved | 0 |
| pylint-dev__pylint-4551 | unresolved | 0 |
| django__django-15851 | unresolved | 0 |
| sympy__sympy-13974 | unresolved | 0 |
| sphinx-doc__sphinx-10449 | unresolved | 0 |

## Notes (factual)

- Gold patches were non-empty for all 10.
- Spot-checks of `report.json` show `patch_successfully_applied: true` with `resolved: false` (FAIL_TO_PASS / PASS_TO_PASS failures) — same pattern as the earlier single-instance gold smoke.
- Full n=100 **not started** pending review of this baseline.

## Runner

```text
python -m commscm.experiments.part_vi_b_oracle_gold_patch --mode sample --sample-n 10 --sample-seed 7 --max-workers 2
# full (not run):
# python -m commscm.experiments.part_vi_b_oracle_gold_patch --mode full --max-workers 2
```
