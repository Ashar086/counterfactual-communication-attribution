# RESEARCH_LOG.md

## Status (frozen replay)

**Tag: `v0.3-replay-engine`** — Part II (Replay Engine) is frozen.

Do not further optimize replay unless real-agent work exposes a new bottleneck.

Guarantees: `commscm/REPLAY_ENGINE_GUARANTEES.md` (G1–G5).

### Week 4 research question (next)

> Can communication attribution improve multi-agent architectures more effectively than existing architecture search methods?

Not “implement CCAS.” Everything in Week 4 answers that question.

---

## Week 3 / 3.5 — Replay engine as a systems contribution

### Research question
Can approximate communication attribution recover the exact replay oracle at a fraction of the computational cost?

### Week 3 objective
**Construct benchmarks that isolate the computational bottlenecks of exact replay.**

### Replay Complexity Suite (paper wording)
> A synthetic benchmark generator that independently controls trace length, branching factor, descendant ratio, and shared subgraph density to isolate replay complexity.

### Core systems insight

| Method | Structural evals | Materialization |
|--------|------------------|-----------------|
| Exact Replay | O(N) | O(N) |
| Descendant (pre-COW) | O(\|affected\|) | O(N) |
| Descendant (COW) | O(\|affected\|) | O(\|affected\|) |

### Algorithmic observation (more important than absolute x)
As the total graph grows while the affected subgraph remains sparse, replay cost scales with the affected subgraph rather than the full graph. Speedup increasing with N (8.6x -> 17.1x at 10% descendants) is evidence of that scaling law—not a hardware-dependent headline number.

### Reviewer-proof claim (use this, not “17x faster”)
> Under sparse interventions (~10% affected descendants), Copy-on-Write replay achieves approximately 10–17x wall-clock speedup (increasing with N) by restricting both structural evaluation and graph materialization to the affected subgraph. As the affected ratio approaches one, replay converges to Exact Replay, as expected.

### Narrative
1. Exact replay is correct but expensive.
2. Descendant replay reduces unnecessary structural evaluation.
3. COW removes the graph-materialization bottleneck.
4. Replay complexity now scales with the affected subgraph.
5. Accurate attribution becomes computationally practical.
6. **No surrogate** unless replay remains too expensive on realistic traces after this.
7. **Replay frozen at v0.3** -> Week 4 = CCAS under the architecture-search RQ above.

---

## Week 3.5 — Scaling validation (GATE before CCAS) — PASSED

### Artifact
- Data: `results/week3_5/scaling_validation.json` (local; gitignored `results/`)
- Figures under `results/week3_5/figures/`
- Runner: `python -m commscm.experiments.week3_5_scaling`

### Fixed 10% ratio, vary N

| N | speedup |
|--:|--------:|
| 100 | 8.6x |
| 500 | 9.0x |
| 1000 | 13.0x |
| 2000 | 17.1x |

Sparse interventions -> large gains; dense (ratio -> 1) -> converges to Exact. Both regimes reported.

### Verdict
**Gate passed. Replay frozen.** Next: Week 4 under the architecture-optimization research question.

### Out of scope until forced
- Learned surrogate
- Further replay micro-optimization
- Real LLM benches (major remaining NeurIPS gap)
- New theory unless forced
