# Oracle-patch control — Step 1 feasibility (no implementation)

**Date:** 2026-08-04  
**Scope:** Feasibility only. No experiment code written. Core CommSCM untouched.

---

## (a) Feasible with current infra?

**Conditionally yes for a corrected experiment; no for the literal “gold patch at CR code location” framing.**

| Piece | Verdict |
|-------|---------|
| Load CR-selected edge from VI.B | ✅ Available |
| Load SWE-bench gold `patch` | ✅ Available |
| Inject arbitrary patch into harness | ✅ Supported |
| Reuse VI.B Docker images locally | ❌ Deleted / not present |
| Disk for n=100 re-pull + eval | ⚠️ Tight (~42 GB free); possible with churn, not comfortable |
| Interpretability of “at CR location” | ❌ Conceptual mismatch — see §5 |

**Recommended honest design (if Step 2 proceeds):**  
`oracle_gold_patch` condition = same n=100 instance list, `model_patch := dataset.patch` (gold), scored with existing Docker harness. Optionally report CR `edit_key` / `hit_gold_edge` as **covariates**, not as a spatial apply filter. This answers: *“If synthesis were replaced by gold, does Resolve@1 recover?”* — not *“apply gold only where CR pointed in the repo.”*

---

## 1. Where CR-selected edge is stored

**Artifact:** `results/part_vi_b_official.json`  
**Filter:** `method == "cr_guided"` → **100 rows**

| Field | Meaning |
|-------|---------|
| `edit_key` | e.g. `prune_edge:C3->C4` — **communication** edge edited |
| `cr_top1` | Top attributed event (`C1`/`C2`/`C3`) |
| `gold` | Injected poison gold event id |
| `hit_gold_edge` | Whether edit targeted gold harmful edge (**100/100 True** for CR) |
| `model_patch` | Synthesized patch used in VI.B (not gold) |

`edit_key` distribution: `C1→C2` 37 · `C3→C4` 33 · `C2→C4` 30.

Gold patch is **not** stored in these rows; must be loaded from HF (`patch` → `SWEBenchInstance.gold_patch` in `commscm/adapters/swebench/load.py`).

---

## 2. Gold patch in dataset

✅ Yes. HuggingFace `princeton-nlp/SWE-bench_Verified` field **`patch`**.  
Loader already maps it: `gold_patch=str(row.get("patch") or "")`.

Harness also supports `--predictions_path gold`, which builds predictions from `datum["patch"]` for the whole dataset (`swebench/harness/utils.py`).

---

## 3. Can harness accept a substituted patch?

✅ Yes. Official eval only needs a predictions JSONL with:

- `instance_id`
- `model_name_or_path`
- `model_patch` (any string; applied via `git apply` inside the instance container)

Existing helper: `write_predictions_jsonl` + `run_official_evaluation` in `commscm/adapters/swebench/official_eval.py`.  
No requirement that the patch come from the CommSCM LLM pipeline. No core changes needed.

---

## 4. Disk / compute — reuse vs rebuild

| Item | Status |
|------|--------|
| Free disk | ~**42 GB** C:, ~**41 GB** D: |
| Cached `swebench/sweb.eval.*` images | **None present** (removed earlier during WebArena disk recovery) |
| VI.B eval logs | Present under `logs/run_evaluation/` (~20 run dirs) — **reports only**, not reusable images |
| LLM re-run | **Not required** — only Docker rescoring of gold predictions |
| Image re-pull | **Required** for essentially all 100 instances (11 repos: django 56, sphinx 10, sympy 10, …) |

**Estimated runtime (n=100, max_workers=4):**  
Roughly **similar to VI.B Docker arm** — on the order of **many hours to ~1 day** wall-clock depending on Hub pull latency + per-instance tests (timeout 1800s). Pull phase will dominate first run after image wipe.

**Not a WebArena-scale blocker (~300 GB),** but **not free**: must re-download instance images; risk of disk pressure mid-run (same class of pain as VI.B, milder than WebArena).

---

## 5. Ambiguity: CR edge vs gold patch “location” (critical)

**CR does not localize a file/hunk in the repository.**  
It localizes a **poisoned communication edge** in the multi-agent DAG (planner→coder, reviewer→reviser, etc.).

The gold `patch` is a **full repository unified diff** (often multi-file / multi-hunk). There is **no** stored mapping from `edit_key` → gold hunk path in VI.B artifacts.

Therefore:

- ❌ “Apply gold patch *at* the CR-selected location” is **not** implementable as stated without inventing a new spatial correspondence.  
- ✅ “Replace synthesized `model_patch` with dataset gold `patch` for the same instances (CR condition already hit gold communication edge 100/100)” **is** implementable and is the scientifically coherent control for *synthesis vs attribution*.

**Prior host signal:** gold smoke on `django__django-14672` already returned **resolved=0** on this machine (`THREATS_TO_VALIDITY` E6). So even gold Resolve@1 may be **&lt; 1.0** due to harness/env — experiment remains informative but may not “jump substantially” on every instance.

---

## Summary for go / no-go

| Question | Answer |
|----------|--------|
| Feasible? | **Yes**, as **oracle gold-patch substitution** + Docker resolve@1 on locked n=100 |
| Literal “gold at CR code locus”? | **No** — framing must be corrected |
| Reused | Instance list, CR row metadata, harness wiring, HF gold `patch` |
| Rebuilt | All instance Docker images; new predictions JSONL; new run_id reports |
| Blockers | Image re-pull + disk headroom; possible non-zero gold fail rate (E6) |
| Est. runtime | Hours–~1 day for n=100 @ 4 workers |

**Step 2 not started.** Awaiting approval of the corrected framing before any implementation.
