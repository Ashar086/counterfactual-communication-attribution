# Replay Engine Guarantees

**Status:** Frozen with tag `v0.3-replay-engine`  
**Scope:** Exact Replay, Descendant Replay, Copy-on-Write (COW) materialization  
**Not in scope:** CCAS, learned surrogates, stochastic LLM semantics

This note states the invariants the implementation is designed to preserve. It is not a new theory paper section—it is a contract between the oracle and the approximations so reviewers (and future us) can trust the engine.

---

## G1 — Soft interventions preserve event identity

Every intervention is a typed soft edit of the form

\[
do(m_\chi = m^0_\chi)
\]

applied to an existing event \(C_k\).

- Event id, sender, receiver, channel, time index, and parent set are unchanged.
- Only the message payload (and intervention metadata) may change.
- Literal deletion \(do(C=\emptyset)\) is forbidden.

**Implication:** Counterfactual graphs remain aligned with the factual event inventory; CR is always attributed to a concrete communication event.

---

## G2 — Replay affects only reachable descendants

Let \(G=(V,E)\) be the factual event DAG and \(k\in V\) the intervened event. Define

\[
\mathrm{Desc}(k) = \{ v\in V \setminus \{k\} : k \leadsto v \}.
\]

Descendant Replay recomputes structural mechanisms only for nodes in \(\{k\}\cup\mathrm{Desc}(k)\).

Nodes outside that set are not re-executed.

**Implication:** Structural evaluation complexity is \(O(|\mathrm{affected}|)\), not \(O(|V|)\), when mechanisms dominate cost.

---

## G3 — Unaffected subgraphs are bitwise identical

For every event \(v\notin \{k\}\cup\mathrm{Desc}(k)\):

- The counterfactual view exposes the **same** `CommunicationEvent` object content as the factual DAG (message bytes unchanged).
- Under COW, those nodes are referenced from the factual store and are not re-materialized.

**Check (debug):** comparing messages on the unaffected set must yield exact equality.

**Implication:** Any change in outcome \(Y\) after intervening on \(k\) is attributable only through the affected subgraph.

---

## G4 — COW preserves replay semantics

Copy-on-write / subgraph materialization is an implementation of the counterfactual **view**, not a change of semantics.

- Exact Replay builds a full concrete `EventDAG`.
- Descendant+COW builds an `OverlayEventDAG`: overrides for affected nodes; read-through to factual for the rest.
- Outcome functions that depend only on `.events` (message payloads over the event set) see the same logical counterfactual state.

Eager `materialize()` may be used for serialization; it is not required on the hot path and must not alter rewards.

**Implication:** Wall-clock may change; CR values on deterministic mechanisms must not.

---

## G5 — Descendant Replay equals Exact Replay on deterministic traces

On traces where:

1. structural mechanisms are deterministic functions of (event, parent messages), and
2. the outcome \(Y\) is a deterministic function of the event messages,

Descendant Replay (with or without COW) must return the same counterfactual reward—and therefore the same CR / ΔY ranking—as Exact Replay for every soft intervention.

**Empirical contract (Week 3 suite):** agreement on counterfactual rewards; Kendall τ / Spearman ρ = 1.0 on deterministic Replay Complexity and random synthetic DAGs.

**Non-claim:** equality under stochastic LLM sampling, nondeterministic tools, or underspecified mechanisms.

---

## Complexity table (frozen)

| Method | Structural evals | Materialization |
|--------|------------------|-----------------|
| Exact Replay | \(O(N)\) | \(O(N)\) |
| Descendant (pre-COW) | \(O(\|\mathrm{affected}\|)\) | \(O(N)\) |
| Descendant (COW) | \(O(\|\mathrm{affected}\|)\) | \(O(\|\mathrm{affected}\|)\) |

**Algorithmic claim (not a hardware claim):** as \(N\) grows while interventions remain sparse (\(|\mathrm{affected}|/N\) small), replay cost scales with the affected subgraph rather than the full graph.

---

## Freeze policy

Do **not** further optimize the replay engine unless real-agent experiments reveal a new bottleneck.

Diminishing returns on another constant-factor win will not strengthen the paper. Next work answers the Week 4 research question (CCAS), not more replay micro-optimization.

## Related artifacts

- Implementation: `commscm/estimators/replay.py`
- Suite: `commscm/benchmarks/replay_complexity.py`
- Scaling: `results/week3_5/scaling_validation.json`, `results/week3_5/figures/`
- Research log: `RESEARCH_LOG.md`
