# CommSCM — FREEZE.md

## One-sentence contribution

**Counterfactual Communication Attribution:** a causal framework that attributes failures to typed information-flow events and uses those attributions to optimize multi-agent communication architectures.

## Paper structure

```
Problem
  → Communication Attribution        (Part I)  ✅ Frozen
  → Efficient Attribution Engine     (Part II) ✅ Frozen
  → Architecture Optimization        (Part III) ⏳ Week 4
  → Real-agent Validation            ⏳ External validity
```

| Part | Content | Status |
|------|---------|--------|
| I — Attribution | IF-C-SCM, typed events, unified CR, exact oracle | Frozen (v0.2*) |
| II — Replay Engine | Descendant, COW, Replay Complexity Suite, scaling | Frozen (`v0.3-replay-engine`) |
| III — Architecture Optimization | CCAS | Interfaces + hypotheses pre-registered |

## Permanent locks

| Component | Decision | Change? |
|-----------|----------|---------|
| Atomic unit | Typed event \(C_k\) with channel \(\chi\) | No |
| SCM | Time-indexed event DAG | No |
| Intervention | Typed soft \(do(m_\chi = m^0_\chi)\) | No |
| Event “removal” | Null-input (not \(\emptyset\)) | Locked |
| Responsibility | **One** CR | No separate CR_e |
| Optimization | CCAS | No |
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

> Did a real-agent experiment force this change?

If **no** → do not touch it.

## Discipline

**No new definitions unless an experiment forces them.**

## CR definition (Week 2 exact)

\[
\mathrm{CR}(k) = Y_{\mathrm{factual}} - Y_{\mathrm{counterfactual}},\quad
\Delta Y(k) = Y_{\mathrm{counterfactual}} - Y_{\mathrm{factual}}
\]

Rank by **ΔY descending**.

## Week 2 freeze

Tags: **v0.2-exact-replay** · **v0.2.1-week2-close**

## Week 3 / 3.5 freeze — Replay Engine

Tag: **v0.3-replay-engine**  
Guarantees: `commscm/REPLAY_ENGINE_GUARANTEES.md` (G1–G5)  
Do not optimize replay further unless real-agent work exposes a new bottleneck.

## Week 4 — pre-registered science (not “implement CCAS”)

Document: **`commscm/WEEK4_PREREGISTRATION.md`**

**RQ:** Can communication attribution improve multi-agent architectures more effectively than existing architecture search methods?

| ID | Hypothesis |
|----|------------|
| H1 | CCAS identifies harmful communication pathways more accurately than reward-only methods |
| H2 | CCAS achieves equal or better task success with fewer architectural modifications |
| H3 | Verifier insertion only when \(\mathrm{Utility}(V)>1\) and reduces task loss |

**Baselines:** GPTSwarm, AgentPrune, G-Designer, MaAS, Static verifier  
**Ablations:** CCAS, CCAS−CR, CCAS−Verifier, Random edits

Biggest remaining risk: **external validity** (real traces → attribution → better architecture → better outcome).
