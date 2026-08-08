# CommSCM — Claims Ledger

**Purpose:** Permanent ledger of what the paper may assert. Prevents accidental overclaiming during writing.  
**Rule:** A claim may appear in the abstract **only** if Status = Supported and Evidence is named.  
**Paper rule:** **Nothing enters the paper unless it appears in this ledger** — Abstract, Introduction, Contributions, Results, and Discussion inclusive.  
**Companion:** `FREEZE.md` · `THREATS_TO_VALIDITY.md` · Results draft: `paper/RESULTS.md`

**Status vocabulary**

| Status | Meaning |
|--------|---------|
| Supported | Evidence exists in named artifacts; scoped to evaluated settings |
| Refuted | Directly contradicted by named evidence; must not be claimed as true |
| Pilot | Gate-passing / small-n; body OK with caveat; not abstract headline alone |
| Not supported | Not justified by evidence (broader claim than tested); must not be claimed |
| Open / future work | Empirically unresolved; discuss as limitation, not as finding |
| Not tested | Planned / deferred; must not be claimed |
| Unsupported | Legacy synonym used below for contradicted or never-justified rows |

**Updated:** 2026-08-06 (Week 1 writing) — LF-fixed VI.B n=100 rollup + significance tests synced.

---

## Final status table (Week 1)

| Claim | Evidence | Status | Abstract? |
|-------|----------|--------|-----------|
| CR improves localization / gold-edge hit (controlled + VI.B poison construct) | Week 4–6; Part V; VI.B `part_vi_b_analysis.json`: CR gold-edge **1.00** vs reward-only **0.33** [0.24, 0.42]; RAP=1.00; proxy=0.97 | **Supported** | ✅ with localization / poison-construct scope |
| CR transfers across frameworks (AutoGen, adapter-only) | Part V Stage 3: Top-1=**1.00**, Kendall τ=**1.00** (`part_v_stage3_framework_compare.json`) | **Supported** | ✅ adapter-only scope |
| Replay engine exact (vs oracle on evaluated deterministic settings) | `REPLAY_ENGINE_GUARANTEES.md`; Week 3: τ=ρ=1.00, 0 failures | **Supported** | ✅ |
| Replay optimization preserves attribution; cost tracks affected subgraph | Week 3.5 `scaling_validation.json`: agreement true; speedups in sparse regimes | **Supported** | ✅ (no universal speedup factor) |
| CR improves Resolve@1 on official SWE-bench Verified | LF campaign: CR **0.02** vs RO **0.04** / random **0.03** / static **0.03**; Fisher p≥0.68; MC overall p=0.9776 | **Refuted** | ❌ |
| Patch synthesis/application accounts for majority of failures **in this pipeline** | CR taxonomy: 92/100 apply errors (hunk 41 + path 34 + malformed 17); scoped wording required | **Supported** | ✅ only as scoped limitation / Results — never as universal law |
| Harness / evaluation validity (LF-fixed) | Oracle gold-patch Resolve@1=**0.89** (89/2/9) on same n=100 list | **Supported** | ✅ ceiling / validity scope |
| CommSCM improves end-to-end software repair (general / SOTA) | Null Resolve@1 gap; no leaderboard win | **Not supported** | ❌ |
| Bottleneck intrinsic vs implementation-specific | No oracle-patch+strong-synthesizer separation beyond gold control; WebArena not run | **Open / future work** | ❌ as closed finding |

---

## Full ledger

| Claim | Evidence | Status | Can appear in abstract? |
|-------|----------|--------|-------------------------|
| Information-flow events are a useful causal abstraction for communication attribution **in evaluated settings** | CausalCommBench / synthetic; Weeks 2–6; Parts V–VI | Supported | ✅ |
| Typed soft interventions enable practical counterfactual communication attribution | CR + Week 2–6 / Part V–VI attribution runs | Supported | ✅ |
| Replay reproduces exact oracle on evaluated deterministic settings; cost tracks affected subgraph under sparse interventions | `REPLAY_ENGINE_GUARANTEES.md`; Week 3 / 3.5 | Supported | ✅ |
| CommSCM transfers LangGraph ↔ AutoGen via **adapter-only** changes | Part V Stages 1–4; Top-1=1.00, Kendall τ=1.00 | Supported | ✅ |
| CR-guided single-edit repairs beat reward-only / heuristic / random under the **same single-edit budget** on controlled synthetic, LangGraph, AutoGen, and SWE-bench-**shaped** suites | Week 6; Part V Stage 4; Part VI Stage 4 | Supported | ✅ with “controlled / shaped” scope |
| Sparse / efficient replay reduces cost vs full exact replay in validated scaling regimes | Week 3.5 `results/week3_5/` | Supported | ✅ (no fixed universal speedup) |
| Frozen pipeline end-to-end on live LangGraph (trace → CR → single edit → re-run) | Week 5–6 live; `v0.6-live-repair` | Supported | ✅ |
| H1: CR localizes injected harmful communication better than reward-only (controlled poisons) | Week 4–6; Part V–VI attribution | Supported | ✅ |
| H2-lite: CR-guided single prune/weaken improves outcomes vs baselines (no verifier) | Week 6; Part V/VI repair (controlled) | Supported | ✅ |
| SWE-bench Verified–**shaped** pilot: adapter-only transfer under communication poisons | Part VI Stages 1–4 | Pilot | ❌ as “SWE-bench”; ✅ shaped/pilot only |
| Official SWE-bench Verified: CR localizes injected harmful communication (gold-edge) better than reward-only under the VI.B poison construct | VI.B analysis: CR gold-edge 1.00 vs RO 0.33; proxy 0.97; pipeline_ok 1.00 | Supported | ✅ localization scope only |
| Official SWE-bench Verified: CommSCM improves Resolve@1 vs same-budget baselines | LF n=100: CR 0.02, RO 0.04, random 0.03, static 0.03; non-significant | **Refuted** | ❌ |
| In our implemented end-to-end pipeline, patch synthesis/application accounts for the majority of observed CR-guided failures (92/100) | `part_vi_b_lf_cr_guided_failure_taxonomy.json`; overnight final | Supported | ✅ Results / scoped limitation only |
| LF-fixed harness can register resolves (evaluation validity / ceiling) | Oracle gold Resolve@1=0.89 (89 resolved / 2 unresolved / 9 error) | Supported | ✅ validity/ceiling |
| CommSCM improves end-to-end software repair (general claim) | Contradicted by official Resolve@1 | **Not supported** | ❌ |
| Whether the apply bottleneck is intrinsic to attribution or specific to this synthesizer/pipeline | Gold control shows harness OK; no stronger synthesizer ablation at CR locus | **Open / future work** | ❌ |
| Oracle-patch + strong synthesizer at CR-selected edit raises Resolve@1 beyond baseline synthesizer | Gold-as-model_patch run is harness control, not CR-locus synthesizer ablation | Not tested (partial: harness-only gold) | ❌ |
| H5 (narrow): frozen pipeline localizes harmful communication via CR on official Verified adapter setting | VI.B gold-edge / RAP | Supported | ✅ localization only |
| H5 (end-to-end): single CR-guided edit improves official Verified Resolve@1 | LF Resolve@1 null / non-sig | **Refuted** | ❌ |
| WebArena adapter smoke | `results/part_vi_c_smoke.json` | Supported | ❌ abstract; Methods only |
| WebArena generalization (official env) | VI.C not executed (infra) | Not tested | ❌ |
| Universal framework independence | Only LangGraph + AutoGen | Unsupported | ❌ |
| Theoretical completeness / full identifiability | — | Unsupported | ❌ |
| Replay always 10×–17× faster regardless of workload | Scaling regimes only | Unsupported | ❌ |
| Superiority vs architecture-search | Unfair under single-edit budget | Unsupported | ❌ |
| SOTA on SWE-bench / WebArena | Resolve@1 null; WebArena not run | Unsupported | ❌ |
| Verifier insertion (H3) | Deferred | Not tested | ❌ |

---

## Abstract draft guardrails

Safe skeleton:

> We introduce a communication-centric causal attribution framework (IF-C-SCM, CR, efficient replay, CCAS), show adapter-level transfer across frameworks, and—on official SWE-bench Verified under an LF-fixed harness—find that CR localizes injected harmful communication (gold-edge 1.00 vs reward-only 0.33) while Resolve@1 remains unimproved (CR 0.02 vs baselines 0.03–0.04). In this pipeline, 92/100 CR-guided failures are patch-apply errors; an oracle gold-patch control reaches Resolve@1 0.89, supporting harness validity.

**Do not add:** “improves SWE-bench Resolve@1,” SOTA, universal invariance, intrinsic/universal synthesis bottleneck, WebArena generalization, fixed universal speedups.

---

## Change protocol

1. New evidence → update Status / Evidence; do not silently upgrade without named artifacts.  
2. Abstract ✅ → ❌ only if falsified.  
3. Core method change → completed Falsification Report; re-review every Supported row.  
4. **Scoped wording:** any claim about patch synthesis/application majority failure must say “in our implemented end-to-end pipeline” / “under this evaluation.”
