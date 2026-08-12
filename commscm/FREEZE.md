# CommSCM — FREEZE.md

> **CommSCM is frozen. The remainder of the project is scientific validation, not algorithm development.**

## One-sentence contribution

**Counterfactual Communication Attribution:** a causal framework that attributes failures to typed information-flow events and uses those attributions to optimize multi-agent communication architectures.  
**(CCAS is the application; attribution is the identity.)**

---

## Operating rule (weekly)

> **Stop building CommSCM. Start trying to disprove it.**  
> **Every week answers one scientific question — not one engineering feature.**  
> **Every commit answers a scientific question or improves reproducibility — never “more clever” CommSCM.**  
> **Nothing enters the paper unless it appears in `docs/CLAIMS_LEDGER.md`.**

If the week’s work cannot be stated as a falsifiable question about the frozen method, it is out of scope.

| Phase | Scientific question | Outcome |
|-------|---------------------|---------|
| **VI.B** | Does CommSCM work on official SWE-bench Verified? | Evidence |
| **VI.C** | Does it generalize to WebArena? | Evidence |
| **VII** | What are the method’s limitations? | Evidence |
| **VIII** | Can independent reviewers reproduce the results? | Evidence |

None of the above change IF-C-SCM, CR, Replay, or CCAS without a falsification report.

**Empirical risks only:** official-bench performance · generalization beyond controlled poisons · scale on long/noisy traces.  
**VI.B success →** analysis, WebArena if practical, hostile review, writing. **No new algorithms.**  
**VI.B failure →** falsification report before any core change.

---

## Branch policy (no core commits on main during validation)

| Branch | Role |
|--------|------|
| `main` / `master` | Frozen CommSCM (paper version). **No core-algorithm commits** during validation. |
| `investigation/*` | Temporary debugging / exploratory work only. |

**Allowed on main without falsification report:** adapters, harnesses, evaluation scripts, paper/docs, threats log, claims ledger updates from evidence.

**Forbidden on main without filed `FALSIFICATION_REPORT`:** changes to IF-C-SCM, CR, Replay engine, Attribution algorithm, CCAS operators / scoring thresholds / action space.

**Merge rule:** `investigation/*` → main only when a completed report under `commscm/falsification_reports/` shows a core assumption is genuinely invalid. That audit trail is what reviewers see if methodology ever changes.

---

## Project phase (redefined)

**You are no longer developing CommSCM. You are trying to falsify it.**

```
Frozen Method → Harder Environment → Still Works? → Harder Environment → â€¦
```

| Macro phase | Contents | Status |
|-------------|----------|--------|
| **Phase I — Theory** | IF-C-SCM; typed events; unified CR (soft interventions); replay semantics | âœ… Frozen |
| **Phase II — Efficient Attribution** | Exact / Descendant / Cached / COW Replay; scaling validation | âœ… Frozen |
| **Phase III — Architecture Optimization** | CCAS; single prune/weaken; H1 + H2-lite; no verifier | âœ… Frozen |
| **Phase IV — External Validation** | Live LangGraph; Framework Invariance (AutoGen); SWE-bench Verified–Shaped Pilot | âœ… Frozen |
| **Phase V — Scientific Validation** | Part VI.B Official SWE-bench; Part VI.C WebArena; paper writing | ðŸš§ **Current** |

No algorithm work remains unless falsified via `FALSIFICATION_REPORT.md`.

### Part-level checklist (same ladder)

| Phase | Goal | Status |
|-------|------|--------|
| Part I | Information-Flow SCM + Communication Responsibility | âœ… Frozen |
| Part II | Replay Engine + Efficient Attribution | âœ… Frozen (`v0.3-replay-engine`) |
| Part III | CCAS + Single-Edit Repair | âœ… Frozen (`v0.5-ccas-synthetic`) |
| Part IV | External Validation (LangGraph) | âœ… Validated (`v0.6-live-repair`) |
| â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ | **Evidence gathering below** | â”€â”€â”€â”€â”€â”€â”€â”€ |
| Part V | **Framework Invariance** (AutoGen first instance) | âœ… **PASS** |
| Part VI | **SWE-bench Verified–Shaped Pilot** | âœ… **PASS** — see `PART_VI_BENCHMARKS.md` |
| Part VI.B | **Official SWE-bench Verified** (Docker resolve@1) | â³ **Next** — true external validity |
| Part VI.C | WebArena (official) | â›” Preregistered, not executed (infra); frozen for later |
| Part VII | Paper Writing | â³ Final |

Living threats log: **`commscm/THREATS_TO_VALIDITY.md`**.  
Claims ledger (abstract guard): **`docs/CLAIMS_LEDGER.md`**.  
Falsification gate: **`commscm/FALSIFICATION_REPORT.md`**.  
Part V plan: **`commscm/PART_V_FRAMEWORK_INVARIANCE.md`**.  
Part VI plan: **`commscm/PART_VI_BENCHMARKS.md`**.  
Part VI.B prereg (H5): **`commscm/PART_VI_B_PREREGISTRATION.md`**.  
Status brief: **`commscm/STATUS_AFTER_PART_V.md`**.

**Focus from here:** strengthen external evidence (official benches, scale, CIs) — **not** expand the method.

**Phase name:** Evidence accumulation. Expand only if a higher-level experiment falsifies a lower level — otherwise test the frozen artifact.

---

## Advising rules (from today onward)

### 1. No more internal benchmarks

Do **not** create another synthetic, shaped, or framework-specific suite unless an **official** benchmark exposes a concrete gap logged in `THREATS_TO_VALIDITY.md`.  
Every new experiment must increase **external** credibility.

### 2. Official benchmark first

Immediate priority order:

1. Finish **Part VI.B preregistration** (`PART_VI_B_PREREGISTRATION.md`) — fill all `UNLOCKED` fields and sign.  
2. Run the official evaluation **exactly** as preregistered.  
3. Report results honestly — including if weaker than the shaped pilot.

Value = showing the frozen method survives **outside** our experimental ecosystem.

### 3. Failures are first-class results

If an official bench reveals a weakness: **do not fix the core immediately.**

1. File a falsification report (`FALSIFICATION_REPORT.md` → `falsification_reports/`).  
2. Name the violated assumption.  
3. Classify: implementation bug · adapter limitation · genuine CommSCM limitation.  
4. Only then consider a core change (and update `docs/CLAIMS_LEDGER.md`).

Honest FAIL / limitation > silent repair.

### 4. Paper writing may begin now

Method sections are frozen; results/discussion evolve. Draft in parallel with VI.B:

| Section | Status |
|---------|--------|
| Introduction | Draftable now (ledger-scoped claims) |
| Related Work | Draftable now (distinguish credit assignment / arch-search / workflow opt) |
| Problem Formulation | Frozen |
| IF-C-SCM | Frozen |
| Communication Responsibility | Frozen |
| Replay Engine | Frozen |
| CCAS | Frozen |
| Experimental Setup | Draftable now; lock VI.B protocol before results |
| Results / Discussion | Evolve with VI.B / VI.C |

Outline: `commscm/PAPER_OUTLINE.md`.

### 5. Hostile review before submission

Before targeting NeurIPS (or similar), commission an external reviewer with top-venue experience:

> Assume you are rejecting this paper. Find every weak assumption, unclear claim, unfair comparison, missing experiment, and theoretical gap.

Do this **after** official-bench results exist; do not substitute another month of implementation for hostile critique.

### What would change confidence next

Not hardware months for WebArena. **Paper polish** (theory, figures, CIs, repro package) + **hostile review** + submit. VI.C remains frozen for future execution when capacity exists. Optional later: oracle-patch control on SWE path.

---

## Evidence ladder (frozen)

| Level | Status | Purpose |
|-------|--------|---------|
| Synthetic oracle | âœ… Complete | Validate causal attribution against known ground truth |
| Replay scaling | âœ… Complete | Validate computational efficiency under sparse interventions |
| Live LangGraph | âœ… Complete | Show end-to-end feasibility on a live framework |
| Framework invariance (AutoGen) | âœ… Complete | Test abstraction independence under adapter-only transfer |
| SWE-bench Verified–Shaped Pilot | âœ… Complete | Pilot external validity (controlled / inspired — not official) |
| Official SWE-bench Verified | âœ… Complete (Part VI.B CLOSED — partial: localization âœ…, Resolve@1 âŒ) | Public benchmark; honest null Resolve@1 |
| WebArena | â›” Preregistered, **not executed** (infra) — protocol frozen for later | Limitation â‰  method failure |

### Ladder revisit rule

> **A lower level cannot be revisited unless a higher-level experiment falsifies it.**

Consequences:

- Do not re-tune IF-C-SCM / CR / Replay / Attribution / CCAS because a lower-level metric “could be nicer.”
- Adapter/harness bugs may be fixed without climbing down the ladder.
- Genuine core defects exposed by a higher level → log in `THREATS_TO_VALIDITY.md` **before** any core change; that change is a finding, not product polish.

### Do not touch (unless a higher-level experiment exposes a genuine flaw)

| Component | Touch? |
|-----------|--------|
| IF-C-SCM | No |
| Communication Responsibility | No |
| Replay engine | No |
| Attribution algorithm | No |
| CCAS operators (`prune_edge` / `weaken_edge` only) | No |

**Hard gate:** opening any of the above requires a completed **`FALSIFICATION_REPORT.md`** (copy under `commscm/falsification_reports/`) answering:

1. Which benchmark exposed the issue?  
2. Which assumption failed?  
3. Why can’t it be handled in an adapter?  
4. Why is a core change scientifically necessary?

If that report cannot be written, **the method stays frozen.**

Every core change must also update **`docs/CLAIMS_LEDGER.md`**.

---

## Claims matrix (frozen for paper + reviewers)

**Authoritative per-claim table for the paper:** `docs/CLAIMS_LEDGER.md` (Claim · Evidence · Status · Abstract?).  
Summary MAY / MUST NOT below; ledger wins on conflicts.

Ask: *what can we defend in front of skeptical reviewers?* — not *did it pass?*

| We MAY claim | We MUST NOT claim (yet) |
|--------------|-------------------------|
| Information-flow events provide a useful causal abstraction for communication attribution in the **evaluated settings**. | Information-flow events are the universally correct causal abstraction for all multi-agent systems. |
| Typed soft interventions enable practical counterfactual communication attribution. | Our counterfactual formulation is theoretically complete or identifiable in all settings. |
| The replay engine reproduces exact replay on the evaluated **deterministic** settings while reducing computational cost under sparse interventions. | Replay is always 10×–17× faster regardless of workload. |
| CommSCM transfers between LangGraph and AutoGen using **adapter-only** changes. | CommSCM is framework-independent in general. |
| On our controlled synthetic, LangGraph, AutoGen, and **SWE-bench-shaped** evaluations, CR-guided edits outperform reward-only, heuristic, and random baselines under a **single-edit budget**. | CommSCM outperforms existing architecture-search methods or achieves state-of-the-art performance. |
| Framework invariance was demonstrated on the **evaluated** frameworks. | Framework invariance has been established for all agent frameworks. |

### Paper evidence framing (preferred narrative)

Emphasize progression, not perfect scores:

> Weeks 1–2 formalized IF-C-SCM and an exact attribution oracle; Weeks 3–3.5 validated efficient replay (including copy-on-write scaling); Week 4 introduced CCAS on controlled synthetics; Weeks 5–6 validated localization and single-edit repair on live LangGraph; Part V transferred the frozen pipeline to AutoGen via adapters only; Part VI.B tests the frozen method on official external benchmarks rather than extending it.

Shorter abstract-friendly form:

> We evaluate CommSCM through progressively stronger settings: (1) synthetic causal traces with known ground truth, (2) live LangGraph executions, (3) framework transfer to AutoGen using adapter-only changes, and (4) official public benchmarks. Across these settings we ask whether the frozen attribution pipeline continues to localize harmful communication and guide effective single-edit repairs under a constrained action budget.

### Remaining blockers before submission

1. **Part VI.B** Official SWE-bench Verified (prereg → run → honest report).  
2. **Part VI.C** WebArena (or second official bench).  
3. Larger-scale evaluation + confidence intervals where claimed.  
4. Finish method/setup drafting; results after VI.B.  
5. Hostile external review (reject-mode) before camera-ready aims.

Algorithm development and new internal benches are **not** on this list.

---

## Frozen pipeline (do not change)

Only the *environment* changes. The methodology stays fixed:

```
Trace Extraction
        â†“
Counterfactual Attribution
        â†“
Single Architecture Edit   (prune_edge | weaken_edge)
        â†“
Evaluation
```

| Environment | Status |
|-------------|--------|
| LangGraph | âœ… Validated |
| **AutoGen** (Part V — first invariance instance) | âœ… PASS (Stages 1–4) |
| CrewAI (additional invariance evidence) | â³ Optional; after official benches preferred |
| SWE-bench Verified–**shaped** pilot | âœ… Part VI PASS |
| Official SWE-bench Verified (resolve@1) | â³ Part VI.B |
| WebArena | â³ Part VI.C |
| Architecture-search baselines | âŒ Unfair under single prune/weaken budget — document skip; compare only same-budget baselines |

---

## Out of scope (until breadth validation is complete)

Explicit prohibitions against scope creep:

| Forbidden | Why |
|-----------|-----|
| No new attribution definitions | Results must not be products of continuous CR tuning |
| No replay-engine modifications | Unless a benchmark exposes a **reproducible defect** |
| No verifier insertion (H3) | Deferred until current validation is complete |
| No surrogate estimators | Unless replay becomes the bottleneck on real benchmarks |
| No new CCAS operators | Feature-frozen; single-edit prune/weaken only |
| No multi-edit search loops / adaptive policies | Week 6 scope was exactly one edit |
| No learned repair policies | Not the paper identity |

---

## Permanent locks

| Component | Decision | Change? |
|-----------|----------|---------|
| Atomic unit | Typed event \(C_k\) with channel \(\chi\) | No |
| SCM | Time-indexed event DAG | No |
| Intervention | Typed soft \(do(m_\chi = m^0_\chi)\) | No |
| Event “removal” | Null-input (not \(\emptyset\)) | Locked |
| Responsibility | **One** CR | No separate CR_e |
| Optimization | CCAS (propose → single apply) | No |
| Bench stack | CausalCommBench + public agent benches | No |

## Frozen interfaces (Part III boundary)

```
AttributionEngine.score(trace) -> AttributionReport
ArchitectureOperator.propose(trace, report) -> ArchitectureProposal
ArchitectureOperator.apply(architecture_id, proposal) -> architecture_id'
```

- Schemas: `commscm/attribution/report.py`, `commscm/ccas/interfaces.py`
- CCAS consumes **AttributionReport only** — no replay-engine leakage
- Edit kinds: closed set in `ArchitectureEditKind`

**Never reshape these** unless a real-agent experiment forces it.

## Foundation protection rule

Before modifying IF-C-SCM, CR, soft interventions, or replay:

> Did a real-agent / breadth experiment force this change?

If **no** → do not touch it.

## Discipline

**No new definitions unless an experiment forces them.**

---

## CR definition (Week 2 exact)

\[
\mathrm{CR}(k) = Y_{\mathrm{factual}} - Y_{\mathrm{counterfactual}},\quad
\Delta Y(k) = Y_{\mathrm{counterfactual}} - Y_{\mathrm{factual}}
\]

Rank by **Î”Y descending**.

## Attribution space vs action space (Part IV lock)

| Space | Contents | Role |
|-------|----------|------|
| Attribution | All events (incl. exogenous roots) | CR may blame a root cause |
| Action | Controllable agentâ†”agent edges only | Live prune/weaken |

---

## Tags

| Tag | Milestone |
|-----|-----------|
| `v0.2-exact-replay` / `v0.2.1-week2-close` | Part I |
| `v0.3-replay-engine` | Part II (G1–G5) |
| `v0.4-pre-ccas` | Part III interfaces |
| `v0.5-ccas-synthetic` | CCAS feature freeze (H1 + H2-lite) |
| `v0.6-live-repair` | Part IV LangGraph live single-edit repair |

## Reference docs

- Claims ledger: `docs/CLAIMS_LEDGER.md`
- Decision log: `docs/DECISION_LOG.md`
- Reproducibility: `REPRODUCIBILITY.md`
- Falsification report template: `commscm/FALSIFICATION_REPORT.md`
- Paper outline: `commscm/PAPER_OUTLINE.md`
- Week 4: `commscm/WEEK4_PREREGISTRATION.md`
- Week 5: `commscm/WEEK5_EXTERNAL_VALIDITY.md`
- Week 6: `commscm/WEEK6_PREREGISTRATION.md`
- Part V: `commscm/PART_V_FRAMEWORK_INVARIANCE.md`
- Part VI: `commscm/PART_VI_BENCHMARKS.md`
- Part VI.B prereg (H5): `commscm/PART_VI_B_PREREGISTRATION.md`
- Part VI.B results: `commscm/PART_VI_B_RESULTS.md`
- Part VI.C WebArena: `commscm/PART_VI_C_WEBARENA.md`
- Status: `commscm/STATUS_AFTER_PART_V.md`
- Threats: `commscm/THREATS_TO_VALIDITY.md`
- Replay guarantees: `commscm/REPLAY_ENGINE_GUARANTEES.md`
- Log: `docs/RESEARCH_LOG.md`
- Repo banner: `README.md`
