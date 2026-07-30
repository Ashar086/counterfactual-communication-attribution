# RESEARCH_LOG.md

## Status

| Part | Status |
|------|--------|
| I — Attribution | ✅ Frozen (v0.2*) |
| II — Replay Engine | ✅ Frozen (`v0.3-replay-engine`) |
| III — interfaces | ✅ Frozen (`v0.4-pre-ccas`) |
| III — Phase A / H1 | ✅ PASS |
| III — Phase B | ✅ PASS |
| III — Phase D / H2-lite | ✅ PASS (iterative prune loop; no full baselines yet) |

Foundation rule: touch Parts I–II only if a real-agent experiment forces it.

---

## Week 4

### RQ
> Can communication attribution improve multi-agent architectures more effectively than existing architecture search methods?

### Phase A / H1
CR-guided P@1=1.00 vs reward-only 0.00 vs random ~0.12.

### Phase B
Single top-1 edit apply. CR hits gold edge 100% on chain suite.

### Phase D / H2-lite (iterative CCAS)
Loop: attribute → propose → apply first valid `prune_edge` → repeat (budget=4).
Suite: multi-path fault (both branches must be cut). Terminal sink must stay attached.

| Method | success | success@2 | edits\|ok | goldHit |
|--------|--------:|----------:|----------:|--------:|
| Random | 0.97 | 0.67 | 2.38 | 0.50 |
| Reward-only | 1.00 | 1.00 | 2.00 | 0.00 |
| CR-guided | **1.00** | **1.00** | **2.00** | **2.00** |

CR matches best success/edit efficiency and is the only method that systematically cuts the gold harmful pathways.

**H2-lite gate: PASS**

Verifier insertion held for H3. Full GPTSwarm/AgentPrune/G-Designer/MaAS bakeoff still ahead. Real-agent validation still the biggest gap.

### Artifacts
- `python -m commscm.experiments.week4_h1`
- `python -m commscm.experiments.week4_phase_b`
- `python -m commscm.experiments.week4_phase_d`

---

## Tags
- `v0.3-replay-engine` — Part II frozen
- `v0.4-pre-ccas` — Part III interfaces + pre-reg (no CCAS at tag time)
