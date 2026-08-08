# Part VI.B — Official SWE-bench Verified Preregistration

**Status:** **EXPERIMENT FROZEN** (signed 2026-08-02). Operational fields locked below. Do not change without a dated amendment + falsification path.  
**Authority:** This file supersedes the checklist stub in `PART_VI_BENCHMARKS.md`.  
**Identity:** Counterfactual Communication Attribution (frozen).  
**Governance:** `FREEZE.md` · `CLAIMS_LEDGER.md` · `FALSIFICATION_REPORT.md`

**Preregistration philosophy:** Measure reality under a frozen protocol. Do **not** preregister absolute performance floors (e.g. RAP ≥ 0.5). Report estimates with confidence intervals and transparent baseline contrasts.

---

## Research Question

> Does the frozen CommSCM pipeline remain effective on the **official** SWE-bench Verified benchmark (`resolve@1`) **without modifying the core method**?

---

## Hypothesis (H5)

The frozen CommSCM pipeline localizes harmful communication events and improves task outcomes through a **single communication-guided architecture edit** on official SWE-bench Verified tasks.

**Scope note:** H5 is about transfer of the frozen pipeline under the official harness — not SOTA, not architecture-search superiority, not universal framework independence (`CLAIMS_LEDGER.md`).

---

## Frozen Components

| Component | Locked |
|-----------|--------|
| IF-C-SCM | Yes |
| Communication Responsibility (CR) | Yes |
| Replay Engine | Yes |
| Attribution algorithm | Yes |
| CCAS operators (`prune_edge` / `weaken_edge` only) | Yes |
| Scoring thresholds | Yes |
| Action space (controllable agent↔agent edges; same exclusions as Part VI shaped) | Yes |

Any required modification must first be documented in a **`FALSIFICATION_REPORT.md`**.

---

## Evaluation Protocol

### Benchmark

**Official SWE-bench Verified** — Docker-based evaluation with community metric **`resolve@1`**.

Never report Part VI shaped-pilot metrics as official Verified results.

### Pipeline (locked)

```
Instance (Verified)
    → Multi-agent execution (adapter)
    → RunTrace extraction
    → Frozen CR attribution
    → Single prune/weaken (CR-guided or baseline)
    → Re-run under same budget
    → Official Docker resolve@1 (+ attribution metrics when gold exists)
```

Adapter/harness only. Core unchanged.

### Task Selection — LOCKED

| Field | Locked value |
|-------|----------------|
| Number of tasks (n) | **100** |
| Selection procedure | Deterministic shuffle of **full** `test` split, then first 100 |
| Inclusion / exclusion | All Verified `test` instances eligible; exclude mid-run **only** if official harness cannot execute that instance in this environment — list any exclusion in `results/part_vi_b_exclusions.json` **before** substituting; do **not** prefer “easy” difficulty (unlike shaped pilot) |
| Instance list artifact | `results/part_vi_b_instance_list.json` (**written 2026-08-02**) |
| Selection seed | **42** |
| Dataset | `princeton-nlp/SWE-bench_Verified` · split `test` · N_pool=500 |

First five IDs (integrity check): `django__django-14672`, `sphinx-doc__sphinx-10449`, `django__django-11299`, `django__django-14493`, `django__django-11551`.

### Execution lock sheet — LOCKED

Same config for factual runs, attribution support paths, and every baseline method.

| Field | Locked value |
|-------|----------------|
| SWE-bench Verified dataset | `princeton-nlp/SWE-bench_Verified` (HF); split `test` |
| Official evaluation harness | GitHub `SWE-bench/SWE-bench` @ commit **`f7bbbb2ccdf479001d6467c9e34af59e44a840f9`** (main as of lock date) |
| Docker images | Namespace **`swebench`** (DockerHub prebuilt instance images, x86_64). **Per-instance digests** recorded at first pull into `results/part_vi_b_docker_digests.json` (no mid-run retag). ARM hosts: build locally with harness `--namespace ''` and record local digests the same way |
| LLM name | **`gpt-4o-mini`** |
| Model / checkpoint version | OpenAI `gpt-4o-mini` (API snapshot as returned in response `model` field; log per run) |
| API provider + version | OpenAI Chat Completions API · `openai` Python package **2.51.0** (lock machine); pin via `pip freeze` at run start → `results/part_vi_b_pip_freeze.txt` |
| Temperature | **0.0** |
| Top-p | **1.0** |
| Max tokens (completion) | **4096** |
| Max context | Provider default for `gpt-4o-mini` (do not truncate Verified problem statements for VI.B — unlike shaped overnight cap) |
| Random seeds | Selection **42**; baseline RNG seed = `run_idx`; LLM seed env `LLM_SEED=42` when supported; log actual seeds per row |
| Seed policy | Deterministic selection + temp 0.0; residual API nondeterminism logged; stability subset uses fixed seed list below |
| Hardware | Windows 10 (build 26200) host; Docker evaluations via **Docker Desktop / WSL2 Linux containers** (or Linux CI with ≥16 GB RAM, ≥120 GB disk per SWE-bench guidance). Record exact host in run log |
| Prompt template id / path / hash | CommSCM SWE-bench adapter prompts in `commscm/adapters/swebench/pipeline.py` at signed core commit; sha256 recorded in `results/part_vi_b_prompt_hashes.json` at run start |
| Timeouts | Per-agent LLM call **120 s**; per-task wall-clock **30 min**; Docker eval per instance **1800 s** (harness `--timeout 1800`) |
| Runs per task | **1** primary Resolve@1 run per (method × instance); methods: CR, reward-only, random, static |
| Stability reps | **3** reps on first **10** locked instance IDs only; temperature **0.0**; for Kendall τ (secondary) |

---

## Metrics

### Primary (report with 95% CIs)

| Metric | Definition notes |
|--------|------------------|
| Resolve@1 | Official SWE-bench Verified resolve rate |
| Gold Edge Hit | When a gold harmful edge is defined for the run |
| Repair Attribution Precision (RAP) | Edit targets the attributed harmful communication |

### Secondary (report with 95% CIs where applicable)

| Metric |
|--------|
| P@1 |
| MRR |
| Attribution Stability (Kendall τ) |
| Runtime |
| Latency |

### Exploratory

| Metric |
|--------|
| Token cost |
| Replay cost |
| Failure taxonomy (F1–F6) |

**No absolute metric floors** as PASS/FAIL cutoffs.

---

## Baselines

| Baseline | Included |
|----------|----------|
| Random | Yes |
| Reward-only | Yes |
| Static heuristic | Yes |
| Architecture-search | **No** — unfair under single prune/weaken; document skip |

**Additional baselines:** none.

---

## Statistical Analysis (locked)

**Primary outputs:** point estimates + **95% CIs** + **effect sizes**. p-values secondary.

| Item | Choice |
|------|--------|
| Location | Mean |
| Dispersion | Standard deviation |
| Interval | **95%** CI |
| CI method | Nonparametric bootstrap **B = 10 000**, paired where methods share instances |
| Effect size | Paired mean difference Resolve@1 (CR − baseline); Cohen’s dz |
| Significance (secondary) | Two-sided paired permutation test (Wilcoxon if needed), α = 0.05; **primary contrast: CR vs reward-only Resolve@1** |
| Multiplicity | random / static = exploratory contrasts |

**Do not change tests after observing results.**

---

## PASS Criteria (process integrity)

| # | Criterion |
|---|-----------|
| P0 | Frozen core unchanged; no silent tuning after seeing results |
| P1 | Pipeline execution success on **≥ 95%** of the locked task set |
| P2 | Primary/secondary metrics reported with **95% CIs** + effect sizes for planned contrasts |
| P3 | Transparent comparison vs preregistered baselines under same single-edit budget |
| P4 | Honest write-up in `PART_VI_B_RESULTS.md` + `CLAIMS_LEDGER.md` update |

Scientific outcomes (who wins on Resolve@1/RAP) are **reported**, not exam gates.

---

## FAIL Criteria (integrity)

| # | Condition |
|---|-----------|
| F0 | Core algorithm modification required |
| F1 | Adapter cannot faithfully extract `RunTrace` |
| F2 | Protocol drift mid-run |
| F3 | Reproducibility fails: re-scoring same prediction file changes Resolve@1; or temp-0 stability top-1 agreement **< 0.80** on the 10×3 subset |
| F4 | Cannot report preregistered statistical plan |

Poor Resolve@1 alone ≠ FAIL — it is evidence. File threats / falsification as appropriate.

---

## Threats expected before running (E1–E7)

| ID | Expected possibility |
|----|----------------------|
| E1 | Failures on **long traces** |
| E2 | Attribution **unstable** under residual stochasticity |
| E3 | Faults **not repairable with one edit** |
| E4 | **Adapter information loss** |
| E5 | **Resolve@1** gains much smaller than shaped pilot (or null) |
| E6 | Docker harness constraints dominate |
| E7 | Gold-edge constructs misaligned with resolve credit |

---

## Out-of-Scope

No new attribution definitions, replay optimizations, verifiers, surrogates, CCAS operators, post-hoc threshold tuning, absolute metric PASS floors, or new internal benches.

---

## Decision rule after VI.B (written before seeing results)

Interpretation paths are locked **before** Resolve@1 and related metrics are known. Do not invent a fourth path after looking at the numbers.

### Result-Blind Interpretation Rule

**Before opening VI.B results:**

- The preregistration is frozen.  
- The decision path is frozen.  
- The analysis code is frozen.  
- The metrics are frozen.  

**After opening the results:**

- Only bug fixes that are **demonstrably unrelated to performance** are allowed (e.g. path typos, logging crashes that do not change scores).  
- Any methodological change requires a **`FALSIFICATION_REPORT`**.  
- Any rerun must be explicitly labeled **post hoc** and **cannot replace** the preregistered primary result.  

This prevents unintentional optimization after seeing the answers.

| Outcome | How to recognize (pre-registered) | Action |
|---------|-----------------------------------|--------|
| **Succeeds** | Process PASS (P0–P4); frozen core unchanged; CR vs baselines reported with 95% CIs; no F0–F4 integrity failure; results are scientifically interpretable (strong *or* modest positive signal is fine — not a SOTA requirement) | Proceed to **WebArena (VI.C)** if feasible; then finalize paper from ledger; invite hostile review |
| **Partially succeeds** | Process PASS, but primary contrast is mixed/null, or gains are confined to subsets, or E1–E7 modes dominate some strata while others look fine | **Document** where it works and where it fails (strata, failure modes, CIs). Classify each weakness as **limitation** (paper §Limitations / threats log) vs **candidate falsification**. Reopen core **only** if a filed `FALSIFICATION_REPORT` shows a foundational assumption failed — default is limitation, not redesign |
| **Clearly fails** | F0–F4 integrity failure, or adapter cannot produce faithful `RunTrace`, or protocol cannot be executed as signed without core change, or results are uninterpretable under the preregistered plan | File **`FALSIFICATION_REPORT.md`** immediately; investigate root cause (bench · adapter · method); **only then** consider reopening the frozen core. Prefer honest negative external-validity finding over silent repair |

**Bias guard:** Do not relabel “clearly fails” as “partially succeeds” to avoid a falsification report, or “partially succeeds” as “succeeds” to skip documenting limitations. Ledger updates follow the chosen row; abstract claims stay off until Supported.

**Lifecycle (locked):** Research question → method design → method freeze → preregistration → official evaluation → choose decision path (success / partial / failure) → paper or falsification—never “improve the method because ideas appear.”

---

## Reporting rules

Lead with estimates + 95% CIs + effect sizes. Never conflate shaped Part VI with VI.B. Abstract may mention official Verified only if ledger allows.

---

## Experiment Frozen (immutable record)

| Field | Value |
|-------|-------|
| Experiment Frozen | **Yes** |
| Date | **2026-08-02** |
| Locked by | Project lead (advisor-directed lock via Cursor session) |
| Git commit (last committed core baseline) | **`3cc07f6a935f9aee819064ef37d26918998363ae`** (`v0.6-live-repair` ancestry). Working-tree adapters/docs may advance **without** core IF-C-SCM/CR/Replay/CCAS edits; any core delta still requires falsification report |
| Repository tag (to apply at freeze commit of harness wiring) | **`vi-b-prereg-2026-08-02`** |
| Benchmark version | `princeton-nlp/SWE-bench_Verified` · test · n=100 · seed=42 |
| Model version | `gpt-4o-mini` · temp 0.0 · top_p 1.0 · max_tokens 4096 |
| Docker / harness | `SWE-bench/SWE-bench@f7bbbb2ccdf479001d6467c9e34af59e44a840f9` · namespace `swebench` · digests file at pull |
| n (tasks) | **100** |
| Instance list artifact written? | **Yes** → `results/part_vi_b_instance_list.json` |
| Execution lock sheet complete? | **Yes** |
| All operational fields filled? | **Yes** |

**Run permission:** **Granted** for execution exactly as specified above.

**Amendments after freeze:** none. Append dated rows only under falsification / environment blockage procedure.
