# Week 4 Pre-Registration — CCAS

**Status:** Interfaces frozen (`v0.4-pre-ccas`); Phase A+ implementation follows the tag.  
**Depends on:** Part I (v0.2*), Part II (`v0.3-replay-engine`)  
**Contracts:** `AttributionEngine` → `AttributionReport` → `ArchitectureOperator` → `ArchitectureProposal`

Do not change Part I / II / these contracts unless a **real-agent experiment** forces it.

---

## Research question (only one)

> Can communication attribution improve multi-agent architectures more effectively than existing architecture search methods?

Not: “Implement CCAS.”

---

## Implementation sequence (discipline)

| Phase | Scope | Gate |
|-------|--------|------|
| A | `ArchitectureOperator` → ranked `ArchitectureProposal` only (no graph mutation) | ✅ PASS (H1) |
| B | Single architecture edit apply (`edits[0]` only) | ✅ PASS |
| C | Evaluate **H1** (ranking metrics) | ✅ done with A |
| D | Iterative CCAS loop | **only if H1 succeeds** — not started |

Phase A candidate edit kinds (ranked, not applied): `prune_edge`, `weaken_edge`, `insert_verifier`.

---

## Hypotheses (scientific goals)

### H1 — Attribution quality for architecture search
CCAS identifies harmful communication pathways more accurately than reward-only methods.

### H2 — Efficiency of modification
CCAS achieves equal or better task success with fewer architectural modifications.

### H3 — Verifier insertion discipline
Verifier insertion occurs only when \(\mathrm{Utility}(V) > 1\) and reduces task loss.

---

## Pre-registered success metrics

### H1
| Metric | Definition |
|--------|------------|
| Edge localization precision | Fraction of top-1 proposed edges in the gold harmful-edge set |
| Recall@k | Gold harmful edges recovered in top-k proposals |
| nDCG | Ranking quality over gold harmful edges |
| False positive edit rate | Fraction of top-1 proposals outside the gold set |

### H2 *(later — do not optimize for these in Phase A)*
| Metric | Definition |
|--------|------------|
| Task success | Binary / reward success after edits |
| Number of architecture edits | Edit budget consumed |
| Total token cost | Cumulative LLM/tool tokens |
| Latency | End-to-end wall time |

### H3 *(later)*
| Metric | Definition |
|--------|------------|
| Utility(V) | Pre-registered verifier utility score |
| ΔTask Loss | Change in task loss after verifier insert |
| Additional token cost | Verifier overhead |

Metric drift is forbidden: if a new metric is needed, amend this document and justify it.

---

## Locked baselines (full paper)

| Baseline | Why |
|----------|-----|
| GPTSwarm | Graph optimization |
| AgentPrune | Communication pruning |
| G-Designer | Dynamic topology |
| MaAS | Architecture search |
| Static verifier | Ablation |

### H1 mini-comparison (Phase C — required before iterative CCAS)

| Method | Harmful edge identified? |
|--------|---------------------------|
| Random | … |
| Reward-only | … |
| CR-guided | … |

If CR-guided does not beat reward-only and random on H1 metrics, **stop** — do not build Phase D.

---

## Locked ablations (full CCAS)

| Condition | Removes |
|-----------|---------|
| CCAS | — |
| CCAS − CR | Communication responsibility |
| CCAS − Verifier | Verifier insertion |
| Random edits | All guidance |

---

## Frozen interfaces

```
AttributionEngine.score(trace) -> AttributionReport
ArchitectureOperator.propose(trace, report) -> ArchitectureProposal
ArchitectureOperator.apply(architecture_id, proposal) -> architecture_id'
```

1. CCAS consumes **`AttributionReport` only**.
2. No replay cost fields in `ArchitectureProposal.meta`.
3. Edit kinds: closed set in `ArchitectureEditKind`.

---

## Foundation protection rule

> Did a real-agent experiment force this change?

If no → **do not touch** Parts I–II.
