# RESEARCH_LOG.md

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

### Reviewer-proof claim (use this, not “13× faster”)
> Under sparse interventions (~10% affected descendants), Copy-on-Write replay achieves approximately 10–17× wall-clock speedup (increasing with N) by restricting both structural evaluation and graph materialization to the affected subgraph. As the affected ratio approaches one, replay converges to Exact Replay, as expected.

### Narrative
1. Exact replay is correct but expensive.
2. Descendant replay reduces unnecessary structural evaluation.
3. COW removes the graph-materialization bottleneck.
4. Replay complexity now scales with the affected subgraph.
5. Accurate attribution becomes computationally practical.
6. **No surrogate** unless replay remains too expensive on realistic traces after this.
7. **CCAS only after Week 3.5 gate.**

---

## Week 3.5 — Scaling validation (GATE before CCAS)

### Artifact
- Data: `results/week3_5/scaling_validation.json`
- Figures:
  - `results/week3_5/figures/alignment_vs_ratio.png` — evals / mat nodes / wall-clock vs ratio
  - `results/week3_5/figures/runtime_vs_n.png` — scaling law @ 10% descendants
  - `results/week3_5/figures/runtime_vs_branching.png`
  - `results/week3_5/figures/runtime_vs_shared.png`
- Runner: `python -m commscm.experiments.week3_5_scaling`

### Experiment A: Fixed 10% ratio, vary N ∈ {100, 250, 500, 1000, 2000}

| N | \|affected\| | Exact ms | COW ms | speedup | COW evals | COW mat |
|--:|-------------:|---------:|-------:|--------:|----------:|--------:|
| 100 | 11 | 110 | 13 | 8.6× | 10 | 11 |
| 250 | 26 | 309 | 35 | 8.8× | 25 | 26 |
| 500 | 51 | 858 | 95 | 9.0× | 50 | 51 |
| 1000 | 101 | 2201 | 170 | 13.0× | 100 | 101 |
| 2000 | 201 | 8284 | 484 | 17.1× | 200 | 201 |

**Finding:** COW evals and materialized nodes track \|affected\| exactly across N. Wall-clock speedup *increases* with N under sparse interventions — evidence that the optimization changed scaling behavior, not just a constant-factor win at one size.

N grew 20× (100→2000); \|affected\| grew ~18×; COW runtime grew ~38× (near affected-scale, with overhead); Exact grew ~76× (worse than linear — full-graph topo/materialization).

### Experiment B: Fixed N=500, vary descendant ratio

Primary paper plot: structural evaluations, materialized nodes, and wall-clock vs ratio — visual alignment shows COW changed the algorithm’s scaling.

At ~10% affected (N=500): median speedup ~9.8×.
As ratio → 1: COW converges toward Exact cost (optimizations matter less).

### Experiment C/D: Branching & shared-subgraph density
At fixed N=500, ratio=10%: secondary axes. Descendant ratio remains the dominant driver of when COW helps; branching/sharing matter more for multi-intervention / cache workloads.

### When is Exact Replay expensive?
Whenever N is large **and** structural evaluations are costly (LLM/tool-like), because both evals and materialization are O(N).

### When do replay optimizations matter?
Under **sparse interventions** (small affected subgraph relative to N). That is the practical regime for localizing a small number of communication faults in a long trace.

### Week 3.5 verdict
**Gate passed.** Replay engine is a publishable systems component: bottleneck analysis → COW redesign → scaling evidence.

**Still not NeurIPS-ready overall** — remaining gaps: real multi-agent eval (SWE-bench Verified / WebArena / AgentDojo) and showing attribution → better architectural decisions (CCAS).

**Next:** Week 4 can begin CCAS, built on an attribution engine that is accurate *and* computationally justified.

### Out of scope (unchanged)
- Learned surrogate
- Real LLM benches (until after CCAS skeleton or in parallel track)
- New theory unless forced
