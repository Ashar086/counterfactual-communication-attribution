# Part V — Framework Invariance Validation

**Not** “AutoGen support.” AutoGen is the **first instance** of this test.

**Scientific question:**

> Does CommSCM remain valid when the execution framework changes?

**Falsification mindset:** Under what conditions does the frozen pipeline stop working?

Parts I–IV frozen (`v0.6-live-repair`). Adapter / extractor glue only. See `FREEZE.md`.

---

## Core Invariance Principle

> Any modification to IF-C-SCM, Communication Responsibility, Replay Engine, or CCAS during Part V **automatically constitutes a failed framework-invariance test**, unless independently justified and reported as a limitation in `THREATS_TO_VALIDITY.md`.

No “just one small tweak” to the core.

---

## Execution stages

| Stage | Goal | Repair? |
|-------|------|---------|
| **1** Adapter only | AutoGen → same `RunTrace` API; zero changes outside adapter | No |
| **2** Attribution invariance | Same poison scenarios as LangGraph; P@1, Gold Hit, Stability, replay | No |
| **3** Framework comparison | Same task in LangGraph vs AutoGen; Top-1, Kendall τ, Gold Hit, Stability | No |
| **4** Single repair | Week-6 pipeline on AutoGen (prune/weaken only) — **only if Stage 2–3 hold** | Yes |

**Decision rule**

| Result | Action |
|--------|--------|
| **PASS** | Adapter-only; frozen core unchanged; comparable attribution (+ repair at Stage 4) → move to SWE-bench Verified–shaped pilot (Part VI), then official Verified (Part VI.B) |
| **FAIL** | Do **not** modify CommSCM. Report: what assumption failed? AutoGen-specific? Invalidates IF-C-SCM or only adapter? Can the limitation be stated rather than “fixed”? |

---

## Pre-registration

### RQ
Does the frozen CommSCM pipeline generalize to an independent multi-agent framework **without modifying the core algorithm**?

### H4
The frozen CommSCM attribution (+ single-edit) pipeline transfers to AutoGen using **adapter-only** changes.

### Primary instance
**AutoGen** (message-passing ↔ communication events; community recognition).

### Secondary instance (later evidence)
CrewAI — additional evidence, not the primary invariance claim.

---

## Frozen pipeline (identical across frameworks)

```
Framework Trace
        ↓
RunTrace
        ↓
Counterfactual Attribution   (frozen)
        ↓
Single Edit                  (prune | weaken)
        ↓
Re-run
        ↓
Evaluation
```

Only **trace extraction / live-edit adapters** may differ by framework.

---

## Success criteria (all required)

| # | Criterion |
|---|-----------|
| 1 | No changes to IF-C-SCM |
| 2 | No changes to Communication Responsibility (CR) |
| 3 | No replay-engine modifications |
| 4 | No CCAS modifications |
| 5 | Only trace extraction / adapter code differs |

---

## Failure criteria (scientific findings — do not patch around)

If AutoGen forces modification of IF-C-SCM, replay, attribution, or CCAS:

1. **Stop** — do not silently “improve” CommSCM  
2. Document: *“CommSCM does not currently generalize because…”*  
3. Treat as a paper-worthy **boundary condition**

If Stage 2 attribution fails, classify first:

- adapter implementation  
- missing framework information  
- genuine CommSCM limitation  

---

## Stage details

### Stage 1 — Adapter only
Map AutoGen execution into existing `RunTrace`:
- Typed events (text, tool, memory, retrieval) — **same event schema**
- Preserve timestamps, sender, receiver, channel, payload, context
- Same `RunTrace` API for frozen attribution engine
- **All** framework-specific logic inside `commscm/adapters/autogen/`

Success: **zero changes outside the adapter package** (and Part V docs/experiments that call it).

### Stage 2 — Attribution invariance
Same communication-poison scenarios as LangGraph. Measure P@1, Gold Edge Hit, Attribution Stability, replay correctness. **No repairs.**

### Stage 3 — Framework comparison (required)
Exact same task in LangGraph and AutoGen:

| Metric | LangGraph | AutoGen |
|--------|-----------|---------|
| Top-1 attributed edge | | |
| Attribution ranking (Kendall τ) | | |
| Gold Edge Hit | | |
| Attribution Stability | | |

### Stage 4 — Single repair
Only after attribution matches: CR → one prune/weaken → re-run → evaluate. No verifier. No iterative CCAS.

---

## Evidence hierarchy

```
Synthetic → Live LangGraph (IV ✅) → Independent Framework / AutoGen (V)
         → SWE-bench (VI) → WebArena (VI) → Paper (VII)
```

---

## Status

**H4 PASS** (AutoGen) — Stages 1–4 complete; Core Invariance Principle held (no Part I–III changes).

| Stage | Result |
|-------|--------|
| 1 Adapter | ✅ |
| 2 Attribution | ✅ CR P@1=1.00 |
| 3 Cross-framework compare | ✅ Top-1 agree=1.00, τ=1.00 |
| 4 Single repair | ✅ CR repair=1.00, RAP=1.00 |

Artifacts: `results/part_v_stage{1,2,3,4}_*.json`  
Adapter: `commscm/adapters/autogen/`

Next evidence: Part VI SWE-bench Verified–Shaped Pilot ✅; remaining: Part VI.B Official SWE-bench Verified.
