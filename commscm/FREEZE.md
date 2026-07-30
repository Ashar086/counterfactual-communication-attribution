# CommSCM — FREEZE.md

## One-sentence contribution

**Counterfactual Communication Attribution:** a causal framework that attributes failures to typed information-flow events and uses those attributions to optimize multi-agent communication architectures.

Everything else is supporting machinery:

| Piece | Role |
|-------|------|
| IF-C-SCM | Formalism (time-indexed event DAG) |
| CR | Unified Communication Responsibility |
| CCAS | Optimization algorithm driven by CR |
| CausalCommBench | Controlled eval (+ SWE / WebArena / AgentDojo later) |

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

Tagged conceptually as **v0.2-exact-replay**.

What it proves: exact soft-null CR localizes injected faults on small deterministic DAGs (single-fault P@1=1; multi-fault Recall@2/nDCG@2=1 under graded Y).

What it does **not** prove: stochastic LLMs, long traces, approximate estimators, real AutoGen/LangGraph logs.

Do not revisit Week 2 unless a later experiment exposes a genuine flaw.
