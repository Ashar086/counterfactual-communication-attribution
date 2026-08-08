# RESEARCH_LOG.md

## Phase

**Evidence accumulation** — falsify / validate the frozen artifact; do not expand the method.

> **CommSCM is frozen. The remainder of the project is scientific validation, not algorithm development.**  
> **Stop building CommSCM. Start trying to disprove it.**

> Under what conditions does the frozen CommSCM methodology stop working?

**Weekly rule:** one scientific question per week — not one engineering feature.  
**Branches:** `main`/`master` = frozen paper version; `investigation/*` = exploratory only; core merges require falsification report (`FREEZE.md` § Branch policy).  
**No more internal benchmarks** unless an official bench exposes a concrete gap (`FREEZE.md` advising rules).

**Remaining risks (empirical only):** official-bench performance · generalization beyond controlled poisons · scale on long/noisy traces. Not design questions.

| Phase | Scientific question | Outcome |
|-------|---------------------|---------|
| VI.B | Official SWE-bench Verified? | Evidence |
| VI.C | WebArena? | Evidence |
| VII | Limitations? | Evidence |
| VIII | Independent reproducibility? | Evidence |

**If VI.B succeeds:** analysis, WebArena if practical, hostile review, paper — **no new algorithms.**  
**If VI.B fails:** falsification report → classify (bench / adapter / method) → only then consider core change.

Evidence ladder + revisit rule: `commscm/FREEZE.md` § Evidence ladder.  
**Each week produces one of:** validated experiment · falsification report · paper section · reproducibility improvement.

Claims: `commscm/CLAIMS_LEDGER.md` · Decisions: `DECISION_LOG.md` · Reproduce: `REPRODUCIBILITY.md` ·  
Core changes: `commscm/FALSIFICATION_REPORT.md` · Paper: `commscm/PAPER_OUTLINE.md` ·  
VI.B prereg/results: `PART_VI_B_PREREGISTRATION.md` / `PART_VI_B_RESULTS.md` · VI.C: `PART_VI_C_WEBARENA.md` ·  
**Repo banner:** `README.md`.  
**Next milestone:** Run official SWE-bench Verified **exactly** as signed in `PART_VI_B_PREREGISTRATION.md` (n=100, frozen 2026-08-02) → fill `PART_VI_B_RESULTS.md`. Paper draft: `paper/DRAFT.md`.

## Status

| Phase | Goal | Status |
|-------|------|--------|
| Part I | IF-C-SCM + CR | ✅ Frozen |
| Part II | Replay Engine | ✅ Frozen (`v0.3-replay-engine`) |
| Part III | CCAS + single-edit repair | ✅ Frozen (`v0.5-ccas-synthetic`) |
| Part IV | LangGraph external validation | ✅ Validated (`v0.6-live-repair`) |
| — | *Evidence gathering below* | — |
| Part V | **Framework Invariance** (AutoGen) | ✅ **PASS** (Stages 1–4) |
| Part VI | **SWE-bench Verified–Shaped Pilot** (Stages 1–4) | ✅ **PASS** (adapter-only; not Docker resolve@1) — `PART_VI_BENCHMARKS.md` |
| Part VI.B | Official SWE-bench Verified (`resolve@1`) | ⏳ **Next** — true external validity |
| Part VI.C | Official WebArena | ⏳ After VI.B |
| Part VII | Paper writing | ⏳ Final |

Threats log: `commscm/THREATS_TO_VALIDITY.md` (Internal / Construct / External / Statistical)  
Post–Part V summary: `commscm/STATUS_AFTER_PART_V.md`  
Question: *Does CommSCM remain valid when the execution framework / benchmark changes?*

---

## Claims (defensible wording)

**Canonical matrix:** `commscm/FREEZE.md` § Claims matrix (MAY / MUST NOT).

### Allowed now (after Part V + Part VI shaped pilot)
See `FREEZE.md` / `STATUS_AFTER_PART_V.md`. Headline:

> Frozen CommSCM localizes injected communication faults across synthetic → LangGraph → AutoGen (adapter-only) → SWE-bench-shaped settings; CR-guided single-edit repairs beat same-budget baselines. Prefer progression narrative over absolute rates near 1.00.

### Not allowed yet
Universal framework independence; architecture-search superiority; theoretical completeness/optimality; verifier effectiveness; official SWE-bench Verified / WebArena / SOTA results.

### H1
> CR-guided consistently identifies the causal harmful edge while reward-only does not.

### H2-lite (not full H2)
> Several edit policies can achieve task repair, but only CR-guided consistently repairs via the true harmful communication pathways.

### H4 (Part V — Framework Invariance) ✅
> The frozen CommSCM pipeline transfers to an independent framework (AutoGen) using adapter-only changes — no modifications to IF-C-SCM, CR, replay, or CCAS.

### Week 6 live (conservative paper wording)
> On the controlled Week 6 live LangGraph poison suite, CR-guided single prune/weaken edits repaired failed runs via gold harmful pathways (Gold Edge Hit = 1.00; Repair Attribution Precision = 1.00). These rates are **not** a claim of universal multi-agent performance.

### Benchmark note (paper)
Terminal sink must remain attached; otherwise policies can falsely “repair” by disconnecting the output.

---

## Week 5 — Real LangGraph attribution (no editing)

Plan: `commscm/WEEK5_EXTERNAL_VALIDITY.md`

**Reviewer framing — what Week 5 establishes vs what it does not:**

| Establishes | Does not yet show |
|-------------|-------------------|
| Framework portability (synthetic → offline → live LangGraph; no Part I–III changes) | Subtle / semantic / delayed faults |
| Implementation robustness (102/102, zero stage failures) | Cross-framework (AutoGen / CrewAI) |
| Initial stoch robustness (temp×seed; Attribution Stability harness) | Harder / subtle fault taxonomy |
| Correct localization under *controlled* poisons | Cross-framework + established benches |

### Offline LangGraph-shaped suite (done)
Extractor + sticky recorded mechanisms + score agent events C1–C5 only.

| Method | P@1 |
|--------|----:|
| CR-guided | **1.00** |
| Reward-only | 0.00 |
| Random | 0.33 |

**Week 5 offline gate: PASS** — same claim form as H1: CR identifies the causal harmful event; reward-only does not.

Adapter notes (not Part I/II changes):
- Sticky mechanisms preserve channel-native injections under recorded-trace rematerialization
- Exogenous task node C0 excluded from scoring (avoids root soft-null absorbing blame)

### Live LangGraph+LLM volume (done)
`python -m commscm.experiments.week5_live_langgraph --n-runs 102 --temperature 0.0`
→ `results/week5_live_langgraph.json`

| Metric | Value |
|--------|------:|
| n scored / attempted | 102 / 102 |
| pipeline / extract / attribution OK | 1.00 / 1.00 / 1.00 |
| failure_counts_by_stage | {} |
| CR P@1 | **1.00** |
| Reward-only P@1 | 0.00 |
| Random P@1 | ≈0.20 |
| mean confidence gap (top1−top2 ΔY) | 1.00 |
| By mode (planner/coder/reviewer) | CR 1.00 each (n=34) |

**Week 5 live gate: PASS** — same claim form as H1 on *live* LLM traces (not offline stubs). Still not SWE-bench/WebArena.

### Stochasticity matrix (done)
`python -m commscm.experiments.week5_live_langgraph --stoch-matrix --out results/week5_live_stoch_matrix.json`
Same task (`return_ok`) / mode (`POISON_PLANNER`); temps {0.0, 0.3, 0.7} × seeds {None, 1, 2, 3} = 12 runs.

| Result | Value |
|--------|------:|
| CR top-1 | **C1 on all 12** |
| CR P@1 | 1.00 |
| Reward-only P@1 | 0.00 |
| confidence gap | 1.00 every cell |
| stage failures | none |

**CR stayed stable under LLM stochasticity** on this fixed poison setting — the main Week 5 unknown did not break first.

### Attribution Stability (appendix — done)
`python -m commscm.experiments.week5_live_langgraph --stability --stability-reps 5 --temperature 0.3`
→ `results/week5_attribution_stability.json`

10 tasks × 5 independent seeds (`POISON_PLANNER`, temp=0.3):

| Metric | Value |
|--------|------:|
| mean top-1 agreement vs mode | **1.00** |
| mean top-1 pairwise agreement | **1.00** |
| mean pairwise Kendall τ | **1.00** |
| scored / attempted | 50 / 50 |

Encouraging under controlled planner poison — still not evidence for subtle semantic faults.

### Week 6 — Live single-edit repair (done, frozen)
Plan: `commscm/WEEK6_PREREGISTRATION.md`  
Artifact: `results/week6_live_repair.json` (balanced schedule; n=60)

**Frozen RQ:** Can communication attribution improve a real multi-agent system through a single architecture edit?

**Attribution vs action space:** CR may score all events (incl. exogenous C0); live edits apply only to controllable agent↔agent edges, preferring outbound edges of the top-1 attributed event toward the sink.

| Method | Repair Rate | Gold Edge Hit | Repair Attr. Prec. | Edit Stability (by mode) | Avg ΔTask | Avg ΔLatency (ms) |
|--------|------------:|--------------:|-------------------:|-------------------------:|----------:|------------------:|
| Random | 0.25 | 0.45 | 0.60 | — | +0.25 | −575 |
| Reward-only | 0.30 | 0.00 | 0.00 | — | +0.30 | −159 |
| CR-guided | **1.00** | **1.00** | **1.00** | **1.00** | **+1.00** | −1670 |

**Headline scientific result (prefer over raw repair rate alone):** Gold Edge Hit = 1.00 and Repair Attribution Precision = 1.00 — attribution identified the causally responsible pathway and the edit used that pathway.

Scope caveat: controlled Week 6 live LangGraph benchmark only — not universal performance.

Latency: reported as measured runtime overhead. Token consumption was not instrumented in Week 6 and is left for future work.

**Failure analysis (report, do not hide):** Across the balanced evaluation, CR-guided incurred no F1–F6 failures, while the control policies exhibited failures primarily due to incorrect edge selection or ineffective repairs (F2/F3/F4).

| Code | Meaning | Count |
|------|---------|------:|
| F1 | Attribution incorrect | 0 |
| F2 | Correct attribution, ineffective edit | 15 |
| F3 | Local improvement only | 8 |
| F4 | Stochasticity / no move | 6 |
| F5 | Extraction/runtime | 0 |
| F6 | Benchmark limitation | 0 |

**Week 6 gate: PASS.** Tag: `v0.6-live-repair`. Algorithmic core frozen — no further Week 6 tuning.

### Paper reporting notes
- Prefer Gold Edge Hit + Repair Attribution Precision as the central claim support; qualify absolute repair rates as controlled-suite results.
- Report F1–F6; note CR-guided had none while controls failed mainly via wrong/ineffective edits.
- Latency = runtime overhead only; token cost not instrumented (future work).

### Part V — Framework Invariance (in progress)
Plan: `commscm/PART_V_FRAMEWORK_INVARIANCE.md`  
Threats: `commscm/THREATS_TO_VALIDITY.md`

**Core Invariance Principle:** any Part I–III change during Part V = failed invariance test (unless reported as limitation).

| Stage | Status |
|-------|--------|
| 1 Adapter only | ✅ `commscm/adapters/autogen/` |
| 2 Attribution invariance | ✅ n=30 CR P@1=1.00 vs reward 0 / random ≈0.13 |
| 3 Same-task LangGraph↔AutoGen | ✅ n=15 Top-1 agree=1.00 Kendall τ=1.00 both gold=1.00 |
| 4 Single repair | ✅ n=9 CR repair=1.00 gold hit=1.00 RAP=1.00 > reward/random |

**H4 PASS** — frozen pipeline transferred to AutoGen with adapter-only changes (Core Invariance Principle held).

**Stage 3 table (framework invariance):**

| Metric | LangGraph | AutoGen |
|--------|----------:|--------:|
| Gold Edge Hit | 1.00 | 1.00 |
| Top-1 agreement (cross-framework) | — | **1.00** |
| Mean Kendall τ | — | **1.00** |

**Stage 4 (AutoGen repair):**

| Method | Repair Rate | Gold Edge Hit | Repair Attr. Prec. |
|--------|------------:|--------------:|-------------------:|
| Random | 0.56 | 0.44 | 0.60 |
| Reward-only | 0.56 | 0.00 | 0.00 |
| CR-guided | **1.00** | **1.00** | **1.00** |

### Part VI — SWE-bench Verified–Shaped Pilot ✅ PASS
Plan / results: `commscm/PART_VI_BENCHMARKS.md`

**Verdict:** Frozen CommSCM transfers adapter-only on a SWE-bench-inspired controlled evaluation (Verified *problem statements* + communication poisons; not Docker resolve@1). Treat as **pilot**.

| Stage | Result |
|-------|--------|
| 1 Trace | ✅ HF → RunTrace; CR hit gold |
| 2 Attribution | ✅ n=24 P@1=1.00 MRR=1.00; τ=1.00 |
| 3 Repair | ✅ n=14 repair=1.00 Gold Hit=1.00 RAP=1.00 |
| 4 Baselines | ✅ CR gold-hit 1.00 > static/reward/random; arch-search skipped (unfair) |

**Next:** Part VI.B Official SWE-bench Verified → Part VI.C WebArena. Claims matrix frozen in `FREEZE.md`.

### Paper roadmap
```
Part I–III  Theory / Replay / CCAS              ✅ Frozen
Part IV     LangGraph                           ✅ Validated
Part V      Framework Invariance                ✅ PASS (AutoGen)
Part VI     SWE-bench Verified–Shaped Pilot     ✅ PASS
Part VI.B   Official SWE-bench Verified         ⏳ Next
Part VI.C   Official WebArena                   ⏳
Part VII    Paper (+ Threats to Validity)
```


---

## Tags
- `v0.3-replay-engine` — Part II
- `v0.4-pre-ccas` — Part III interfaces
- `v0.5-ccas-synthetic` — CCAS feature freeze after H1 + H2-lite
- `v0.6-live-repair` — Week 6 live single-edit repair gate PASS
