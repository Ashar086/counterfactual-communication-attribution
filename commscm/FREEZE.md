# CommSCM — FREEZE.md

## One-sentence contribution

**Counterfactual Communication Attribution:** a causal framework that attributes failures to typed information-flow events and uses those attributions to optimize multi-agent communication architectures.

Everything else is supporting machinery:

| Piece | Role |
|-------|------|
| IF-C-SCM | Formalism (time-indexed event DAG) |
| CR | Unified Communication Responsibility |
| Replay engine | Exact + Descendant + COW (Part II) |
| CCAS | Optimization algorithm driven by CR (Part III) |
| CausalCommBench | Controlled eval (+ SWE / WebArena / AgentDojo later) |

## Paper structure (frozen outline)

| Part | Content | Status |
|------|---------|--------|
| I — Attribution | IF-C-SCM, typed events, unified CR, exact replay oracle | Frozen (v0.2*) |
| II — Replay Engine | Descendant replay, COW, Replay Complexity Suite, scaling | **Frozen (v0.3-replay-engine)** |
| III — Architecture Optimization | CCAS | Next (Week 4) |

## Permanent locks

| Component | Decision | Change? |
|-----------|----------|---------|
| Atomic unit | Typed event \(C_k\) with channel \(\chi\) | No |
| SCM | Time-indexed event DAG | No |
| Intervention | Typed soft interventions \(do(m_\chi = m^0_\chi)\) | No |
| Event “removal” | Null-input soft intervention (not \(\emptyset\)) | Locked as null-input |
| Responsibility | **One** CR (content-first via typed soft do) | No separate CR_e |
| Optimization | CCAS | No |
| Bench stack | CausalCommBench + public agent benches | No |

## Discipline

**No new definitions unless an experiment forces them.**

## CR definition (Week 2 exact)

\[
\mathrm{CR}(k) = Y_{\mathrm{factual}} - Y_{\mathrm{counterfactual}},\quad
\Delta Y(k) = Y_{\mathrm{counterfactual}} - Y_{\mathrm{factual}}
\]

Localization ranks by **ΔY descending** (largest improvement when soft-nulled ⇒ top blame).

## Week 2 freeze

Tagged: **v0.2-exact-replay** (oracle) · **v0.2.1-week2-close** (cascade + noise closers).

Present as: **"exact replay implementation validated on controlled synthetic traces"** — never as "100% localization" in a paper abstract.

## Week 3 / 3.5 freeze — Replay Engine

Tagged: **v0.3-replay-engine**

Invariants: see **`commscm/REPLAY_ENGINE_GUARANTEES.md`** (G1–G5).

What it proves (synthetic Replay Complexity Suite):

- Descendant structural evals scale with the affected subgraph.
- COW materialization scales with the affected subgraph (same curve as evals).
- Under sparse interventions, wall-clock speedup **increases with N** (algorithmic scaling, not a one-size microbenchmark).
- Under dense interventions (ratio → 1), cost converges to Exact Replay.

**Do not optimize replay further** unless real-agent experiments expose a new bottleneck.

## Week 4 research question (locked framing)

**Not:** “Implement CCAS.”

**Yes:**

> Can communication attribution improve multi-agent architectures more effectively than existing architecture search methods?

Everything in CCAS must answer that question. Replay is the foundation; CCAS is the missing Part III.
