# RESEARCH_LOG.md

## Status

| Part | Status |
|------|--------|
| I — Attribution | ✅ Frozen (v0.2*) |
| II — Replay Engine | ✅ Frozen (`v0.3-replay-engine`) |
| III — CCAS | ⏳ Interfaces + Week 4 hypotheses pre-registered |

**Foundation rule:** touch IF-C-SCM / CR / replay only if a real-agent experiment forces it.

Guarantees: `commscm/REPLAY_ENGINE_GUARANTEES.md`  
Week 4 pre-reg: `commscm/WEEK4_PREREGISTRATION.md`  
Contracts: `AttributionEngine` → `AttributionReport` → `ArchitectureOperator` → `ArchitectureProposal`

---

## Week 4 research question (locked)

> Can communication attribution improve multi-agent architectures more effectively than existing architecture search methods?

### Pre-registered hypotheses
- **H1:** CCAS identifies harmful communication pathways more accurately than reward-only methods.
- **H2:** CCAS achieves equal or better task success with fewer architectural modifications.
- **H3:** Verifier insertion only when Utility(V)>1 and reduces task loss.

### Locked baselines
GPTSwarm · AgentPrune · G-Designer · MaAS · Static verifier

### Locked ablations
CCAS · CCAS−CR · CCAS−Verifier · Random edits

### Biggest risk
External validity — not replay.

---

## Week 3 / 3.5 — Replay engine (FROZEN)

### Algorithmic observation (primary)
As the total graph grows while the affected subgraph remains sparse, replay cost scales with the affected subgraph rather than the full graph.

| N @ 10% descendants | Speedup |
|--:|--------:|
| 100 | 8.6x |
| 500 | 9.0x |
| 1000 | 13.0x |
| 2000 | 17.1x |

Sparse → large gains; dense (ratio→1) → converges to Exact. Both reported.

### Complexity table

| Method | Structural evals | Materialization |
|--------|------------------|-----------------|
| Exact Replay | O(N) | O(N) |
| Descendant (pre-COW) | O(\|affected\|) | O(N) |
| Descendant (COW) | O(\|affected\|) | O(\|affected\|) |

### Claim form
> Under sparse interventions (~10% affected descendants), Copy-on-Write replay achieves approximately 10–17x wall-clock speedup (increasing with N) by restricting both structural evaluation and graph materialization to the affected subgraph. As the affected ratio approaches one, replay converges to Exact Replay, as expected.

Do **not** further optimize replay unless real-agent work forces it.

### Artifacts
- Runner: `python -m commscm.experiments.week3_5_scaling`
- Local results: `results/week3_5/` (gitignored)
