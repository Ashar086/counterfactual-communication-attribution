# RESEARCH_LOG.md

## Status

| Part | Status |
|------|--------|
| I — Attribution | ✅ Frozen |
| II — Replay Engine | ✅ Frozen (`v0.3-replay-engine`) |
| III — CCAS (synthetic H1 + H2-lite) | ✅ **Feature-frozen** (`v0.5-ccas-synthetic`) |
| H3 verifier | ⏸ Deferred — do **not** implement next |
| IV — External validity | ✅ Week 5 + **Week 6 live repair PASS** (`v0.6-live-repair`) |

---

## Claims (defensible wording)

### H1
> CR-guided consistently identifies the causal harmful edge while reward-only does not.

### H2-lite (not full H2)
> Several edit policies can achieve task repair, but only CR-guided consistently repairs via the true harmful communication pathways.

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
| Initial stoch robustness (temp×seed; Attribution Stability harness) | Localization → edit → better outcome ← **Week 6** |
| Correct localization under *controlled* poisons | Established public benches |

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

Token Δ not instrumented in this run (latency proxy only).

**Failure taxonomy (unsuccessful repairs only; CR had zero):**

| Code | Meaning | Count |
|------|---------|------:|
| F1 | Attribution incorrect | 0 |
| F2 | Correct attribution, ineffective edit | 15 |
| F3 | Local improvement only | 8 |
| F4 | Stochasticity / no move | 6 |
| F5 | Extraction/runtime | 0 |
| F6 | Benchmark limitation | 0 |

**Week 6 gate: PASS.** Tag: `v0.6-live-repair`. No further gating/threshold tuning.

Next (breadth, not algorithms): second framework or public bench; baselines GPTSwarm / AgentPrune / G-Designer / MaAS.

Runners:
- Offline: `python -m commscm.experiments.week5_langgraph_localize`
- Live: `python -m commscm.experiments.week5_live_langgraph --n-runs 102`
- Stoch: `python -m commscm.experiments.week5_live_langgraph --stoch-matrix`
- Stability: `python -m commscm.experiments.week5_live_langgraph --stability --temperature 0.3`
- Week 6: `python -m commscm.experiments.week6_live_repair --n-runs 60`

### Paper roadmap
Synthetic → Offline real-shaped → Live localization ✅ → **Live single-edit repair ✅** → Cross-framework / established benches


---

## Tags
- `v0.3-replay-engine` — Part II
- `v0.4-pre-ccas` — Part III interfaces
- `v0.5-ccas-synthetic` — CCAS feature freeze after H1 + H2-lite
- `v0.6-live-repair` — Week 6 live single-edit repair gate PASS
