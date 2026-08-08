# Part VI.B — Docker harness audit (2026-08-02)

**Purpose:** Diagnose why Resolve@1 was useless before sinking more Docker time.  
**Not a protocol amendment.** Prior Docker arm numbers are **non-primary**.

## Finding 1 — Last-wins collapse (measurement bug)

SWE-bench `run_evaluation` builds `predictions = {instance_id: pred}` (last wins).  
Mixed-method jsonl batches produced reports named only:

`commscm-vi-b-static_heuristic.vi_b_part_vi_b_official_*.json` (15/15)

So every Docker batch scored **static_heuristic only**. Other methods never received Resolve@1.

| Metric (15 batches) | Count |
|---------------------|------:|
| resolved | 0 |
| unresolved | 1 |
| errors | 14 |

## Finding 2 — Error arm cluster

**Harness reports:** 100% of scored rows are the static arm (artifact of Finding 1), not a fair cross-method error comparison.

**Checkpoint patches (n=60, 15×4 methods)** — pre-normalize issue signals:

| Method | missing `a/`/`b/` prefix | `apply_patch` stub |
|--------|-------------------------:|-------------------:|
| cr_guided | 12 | 2 |
| reward_only | 13 | 0 |
| random | 8 | 8 |
| static_heuristic | 13 | 8 |

Interpretation: malformed unified-diff prefixes are **cross-method** (LLM/format), not static-only. Stub pollution is heavier on **random** and **static_heuristic**. Do not interpret the 14/15 Docker errors as “static fails; CR works.”

## Finding 3 — Parallelism (prereg-safe)

Prereg locks harness commit, namespace, timeout 1800s — **not** `--max_workers`.  
Default raised to **4** workers per method eval (same fixed instance list). Expected ~3–4× wall-clock vs `max_workers=1` on Docker Desktop, hardware permitting.

## Fix (adapter/harness only)

- `evaluate_by_method`: one predictions file + one `run_id` per method  
- `normalize_model_patch`: LF + `a/`/`b/` prefixes + strip post-hunk `apply_patch` stubs  
- Runner: `--docker-only`, `--skip-docker`, `--max-workers`

## Resume recipe

```text
# Finish LLM rows without Docker
python -m commscm.experiments.part_vi_b_official_runner --skip-docker --out results/part_vi_b_official.json

# Then score all methods correctly (parallel workers)
python -m commscm.experiments.part_vi_b_official_runner --docker-only --max-workers 4 --out results/part_vi_b_official.json
```
