# Part VI.C — Official WebArena Preregistration

**Status:** **EXPERIMENT FROZEN** (signed 2026-08-04). Operational fields locked below. Do not change without a dated amendment + falsification path.  
**Study type:** **Validation only** — same frozen CommSCM pipeline; adapter/harness only. **No method changes regardless of outcome.**  
**Authority:** This file supersedes the checklist stub in `PART_VI_C_WEBARENA.md`.  
**Identity:** Counterfactual Communication Attribution (frozen).  
**Governance:** `FREEZE.md` · `CLAIMS_LEDGER.md` · `FALSIFICATION_REPORT.md` · VI.B CLOSED (`PART_VI_B_RESULTS.md`)

**Preregistration philosophy:** Measure reality under a frozen protocol. Do **not** preregister absolute performance floors. Report estimates with confidence intervals and transparent baseline contrasts.  
**Lesson from VI.B:** Null end-to-end success does not automatically falsify attribution if failure modes are documented and localize downstream of CR. Scope claims to the ledger.

---

## Research Question

> Does the frozen CommSCM pipeline **generalize beyond software-engineering tasks** to **WebArena** web-agent settings **without modifying the core method**?

---

## Hypothesis (H6)

The frozen CommSCM pipeline localizes harmful communication events under a WebArena multi-agent adapter construct and, under a **single communication-guided architecture edit**, improves (or does not degrade relative to same-budget baselines) **official WebArena task success** when that metric is measurable.

**Scope note:** H6 is about **domain transfer** of the frozen pipeline — not SOTA on WebArena, not universal framework independence, not a claim that VI.B Resolve@1 is rescued (`CLAIMS_LEDGER.md`).

**Split (report both; do not conflate):**

| Layer | Question |
|-------|----------|
| H6a Localization | Under injected communication poisons with gold edges, does CR hit gold better than reward-only / random / static? |
| H6b End-to-end | Does CR-guided single edit improve official WebArena success vs same-budget baselines? |

VI.B showed H5a-style localization can hold while H5b fails. Expect the same split; do not redefine success after seeing numbers.

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
| Action space | Controllable **agent↔agent** edges only. Browser/DOM/tool observations and environment transitions are **exogenous** (not editable by CCAS). Sink / terminal scorer edges excluded from the edit action space (same spirit as Part VI shaped / VI.B). |

Any required core modification must first be documented in a **`FALSIFICATION_REPORT.md`**. Outcome of VI.C — positive, null, or negative — **does not** authorize redesign of IF-C-SCM, CR, Replay, or CCAS.

---

## Evaluation Protocol

### Benchmark — LOCKED

| Field | Locked value |
|-------|----------------|
| Choice | **A — Original WebArena** (Zhou et al., ICLR 2024 / arXiv:2307.13854) |
| Why A | Standard literature reference; not WebArena-Verified (Option B deferred) |
| Repo | GitHub `web-arena-x/webarena` |
| Harness commit | **`dce04686a56253aefba7b18a4fa0937cf1dc987b`** (main as of freeze date) |
| Annotation baseline | Release **`v0.2.0`** (`e32b71e3f5b2463bb102457591bc06c0f2c93acf`) — stable task annotations per upstream README |
| Pool | **812** tasks (`config_files/{id}.json` after `scripts/generate_test_data.py`) |
| Primary metric harness | Official WebArena **functional correctness** evaluators (not LLM-as-judge) |
| Bench digest artifact | `results/part_vi_c_bench_digest.json` (record at env bring-up) |

Never report shaped SWE / VI.B metrics as WebArena results.

### Pipeline — LOCKED

```
WebArena task (locked ID)
    → Multi-agent execution (adapter graph below)
    → RunTrace extraction
    → Frozen CR attribution
    → Single prune/weaken (CR-guided or baseline)
    → Re-run under same budget
    → Official WebArena success (+ gold-edge / RAP)
```

Adapter/harness only. Core unchanged.

### Multi-agent graph + poison — LOCKED

| Role | Node | Role |
|------|------|------|
| Task / intent | C0 | Exogenous task text |
| Planner | C1 | High-level plan / next subgoal |
| Navigator | C2 | Browser actions from observation |
| Critic | C3 | Approve / revise communication |
| Revised navigator intent | C4 | Post-critic action guidance |
| Score | C5 | Official evaluator / success sink (not editable) |

**Default topology:** `C0→C1→C2→C3→C4→C2` (loop bounded by step budget) · `C5` observes outcome only.

| Field | Locked value |
|-------|----------------|
| Communication poison | Inject harmful **C1→C2** (planner→navigator) message; **gold edge = C1→C2** |
| Organic-only arm | Exploratory only; **not** primary contrast |
| Proxy reward | Task-agnostic communication cleanliness / critic approval — **must not** leak official evaluator answers or gold strings |
| Prompt templates | `commscm/adapters/webarena/pipeline.py` (created post-freeze; sha256 → `results/part_vi_c_prompt_hashes.json` at first smoke **before** full run) |

### Task Selection — LOCKED

| Field | Locked value |
|-------|----------------|
| n | **100** (largest affordable locked size; full pool 812) |
| Selection | Deterministic shuffle of **full** pool `{0…811}`, then first 100 |
| Seed | **42** |
| Inclusion | All 812 eligible a priori; exclude mid-run **only** if locked Docker env cannot execute that task — list in `results/part_vi_c_exclusions.json` **before** substituting; do **not** prefer “easy” sites |
| Instance list | `results/part_vi_c_instance_list.json` (**written 2026-08-04**) |
| Site strata | Secondary reporting only (shopping / admin / gitlab / map / reddit / wikipedia as labeled upstream) |

**First five task IDs (integrity check):** `743`, `419`, `231`, `619`, `614`.

### Execution lock sheet — LOCKED

| Field | Locked value |
|-------|----------------|
| LLM | **`gpt-4o-mini`** |
| Temperature / top_p / max_tokens | **0.0** / **1.0** / **4096** |
| API | OpenAI Chat Completions; pin `openai` via `pip freeze` at run start → `results/part_vi_c_pip_freeze.txt` |
| Browser / env | Official WebArena self-hosted Docker sites + Playwright/`ScriptBrowserEnv`; observation **accessibility_tree**; record host OS/RAM/disk in run log |
| Timeouts | Per LLM call **120 s**; per-task wall-clock **30 min**; env reset per upstream guidance between full sweeps |
| Max browser steps / task | **30** (adapter hard cap; log if hit) |
| Runs | **1** primary per (method × instance); methods: CR, reward-only, random, static |
| Stability | **3** reps × first **10** locked IDs; temp **0.0**; Kendall τ secondary |
| Seeds | Selection **42**; baseline RNG = `run_idx`; `LLM_SEED=42` when supported |
| Hardware | Windows 10 (build 26200) host and/or Linux VM with sufficient RAM/disk for WebArena Docker; record exact host in run log |
| Core baseline commit | **`3cc07f6a935f9aee819064ef37d26918998363ae`** (same as VI.B; no IF-C-SCM/CR/Replay/CCAS edits) |

---

## Metrics

### Primary (report with 95% CIs)

| Metric | Definition |
|--------|------------|
| WebArena Success | Official functional success rate (binary per task) |
| Gold Edge Hit | Gold harmful edge hit rate (H6a) |
| RAP | Edit targets attributed harmful communication |

### Secondary

| Metric |
|--------|
| P@1, MRR |
| Attribution Stability (Kendall τ) |
| Runtime / latency |
| Failure taxonomy (adapter / browser / action / attribution / edit / evaluator) |

**No absolute metric floors** as PASS/FAIL cutoffs.

---

## Baselines

| Baseline | Included |
|----------|----------|
| Random | Yes |
| Reward-only | Yes |
| Static heuristic | Yes |
| Architecture-search | **No** — unfair under single prune/weaken; document skip |

---

## Statistical Analysis — LOCKED

| Item | Choice |
|------|--------|
| Location / dispersion | Mean / SD |
| Interval | **95%** CI |
| CI method | Nonparametric bootstrap **B = 10 000**, paired where methods share instances |
| Effect size | Paired mean difference Success (CR − baseline); Cohen’s dz |
| Primary contrast | **CR vs reward-only** on (1) Gold Edge Hit, (2) WebArena Success |
| Multiplicity | random / static = exploratory |

**Do not change tests after observing results.**

---

## PASS Criteria (process integrity)

| # | Criterion |
|---|-----------|
| P0 | Frozen core unchanged; no silent tuning after seeing results |
| P1 | Pipeline execution success on **≥ 95%** of the locked task set (env-up failures listed, not silently dropped) |
| P2 | Primary/secondary metrics with **95% CIs** + effect sizes for planned contrasts |
| P3 | Transparent comparison vs preregistered baselines under same single-edit budget |
| P4 | Honest write-up in `PART_VI_C_RESULTS.md` + `CLAIMS_LEDGER.md` update |

Scientific win/loss on Success is **reported**, not an exam gate.

---

## FAIL Criteria (integrity)

| # | Condition |
|---|-----------|
| F0 | Core algorithm modification required |
| F1 | Adapter cannot faithfully extract `RunTrace` |
| F2 | Protocol drift mid-run |
| F3 | Reproducibility fails (re-score drift / stability top-1 agreement **< 0.80** on 10×3) |
| F4 | Cannot report preregistered statistical plan |

Poor WebArena Success alone ≠ FAIL — evidence. File threats / falsification as appropriate. **Do not** change CommSCM to chase Success.

---

## Threats expected before running (E1–E8)

| ID | Expected possibility |
|----|----------------------|
| E1 | Failures on **long / interactive** traces |
| E2 | Attribution **unstable** under residual stochasticity |
| E3 | Faults **not repairable with one edit** |
| E4 | **Adapter information loss** (DOM / tool / browser actions under-specified as events) |
| E5 | Official Success gains null / much smaller than localization (VI.B pattern) |
| E6 | **Environment / Docker / site** constraints dominate |
| E7 | Gold-edge / poison construct misaligned with Success credit |
| E8 | Browser action synthesis / navigation errors dominate (analogue of VI.B patch-apply bottleneck) |

---

## Out-of-Scope

No new attribution definitions, replay optimizations, verifiers, surrogates, CCAS operators, post-hoc threshold tuning, absolute metric PASS floors, new internal benches, VI.B reruns, or method redesign after seeing VI.C numbers.

---

## Decision rule after VI.C (written before seeing results)

### Result-Blind Interpretation Rule

**Before opening VI.C results:** preregistration, decision path, analysis code, and metrics are frozen.  
**After opening:** only bugfixes demonstrably unrelated to performance; any methodological change requires **`FALSIFICATION_REPORT`**; any rerun labeled **post hoc** and cannot replace the primary result.

| Outcome | Action |
|---------|--------|
| **Succeeds** | Process PASS; interpretable H6a and/or H6b; proceed to hostile review + paper from ledger |
| **Partially succeeds** | Document strata / failure modes (esp. E5/E8); default = **limitation**, not redesign |
| **Clearly fails** | F0–F4 or uninterpretable protocol → file falsification; investigate **adapter vs method** — prefer honest negative external-validity finding over silent repair |

**Bias guard:** Do not relabel clear fail as partial to avoid falsification, or partial as success to skip limitations.

---

## Reporting rules

Lead with estimates + 95% CIs + effect sizes. Never conflate SWE / shaped / VI.B with VI.C. Abstract may mention WebArena only if ledger Status = Supported for that scoped claim.

---

## Experiment Frozen (immutable record)

| Field | Value |
|-------|-------|
| Experiment Frozen | **Yes** |
| Date | **2026-08-04** |
| Locked by | Project lead (advisor-directed lock via Cursor session) |
| Study type | Validation only — frozen CommSCM; no outcome-contingent method changes |
| Git commit (core baseline) | **`3cc07f6a935f9aee819064ef37d26918998363ae`** |
| Repository tag | **`vi-c-prereg-2026-08-04`** (apply when tagging) |
| Benchmark / harness | Original WebArena · `web-arena-x/webarena@dce04686…` · annotation baseline `v0.2.0` |
| Model | `gpt-4o-mini` · temp 0.0 · top_p 1.0 · max_tokens 4096 |
| n / seed / instance list | **100** / **42** / `results/part_vi_c_instance_list.json` |
| Execution lock sheet complete? | **Yes** |
| All operational fields filled? | **Yes** |

**Run permission:** **Granted** for execution **exactly as specified** above (after adapter smoke + prompt hashes recorded).

**Amendments after freeze:** none for method. Append dated rows only under falsification / environment blockage procedure.

---

## Post-freeze execution order

1. Implement `commscm/adapters/webarena/` to match locked graph (no core edits).  
2. Record prompt hashes → `results/part_vi_c_prompt_hashes.json`.  
3. Smoke: 1 locked task end-to-end + `RunTrace` schema check.  
4. Full run → analyze with frozen script → `PART_VI_C_RESULTS.md` → ledger.  
5. **Never** reopen for dislike of numbers.
