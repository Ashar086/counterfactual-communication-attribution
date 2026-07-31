# Week 5 — External validity (attribution on real agent traces)

**Status:** CCAS feature-frozen. No H3. **Week 5 complete** (offline + live volume + stoch). Week 6 = real repair.

---

## Paper roadmap (updated)

```
Synthetic validation
  → Offline real-shaped traces     ✅
  → Live real traces               ✅ (n=102, CR P@1=1.0; stoch stable)
  → Real repair (single-edit)      Week 6
  → Benchmark comparison           later (SWE-bench / WebArena / …)
```

Not: Synthetic → Real → Paper.

---

## Claims

### Offline / engineering validation (not paper headline)
LangGraph-shaped recorded states: CR P@1=1.0 vs reward-only 0.0 — adapter check only.

### Live (paper-relevant) — gate PASS
Live LLM LangGraph executions with injected channel-native poisons; attribution only.
`results/week5_live_langgraph.json` (n=102, temp=0.0):

| Method | P@1 |
|--------|----:|
| CR | **1.00** |
| Reward-only | 0.00 |
| Random | ≈0.20 |

Also: mean confidence gap=1.00; pipeline/extract/attribution OK rates=1.00; no stage failures.
Per poison mode (n=34 each): CR P@1=1.00.

### Stochasticity (appendix)
Same task/mode; temps × seeds (12 cells): CR top-1 = C1 on every cell; reward-only P@1=0.

### Attribution Stability (appendix — reviewer metric)
Per task: K independent live executions → top-1 agreement + mean pairwise Kendall τ.
`results/week5_attribution_stability.json` (10 tasks × 5 reps, temp=0.3, POISON_PLANNER):
mean top-1 agreement = **1.00**, mean pairwise Kendall τ = **1.00**.

---

## Runners

```bash
# Offline adapter check
python -m commscm.experiments.week5_langgraph_localize

# Live volume (default 102 runs)
python -m commscm.experiments.week5_live_langgraph --n-runs 102

# Stochasticity matrix (same task/mode; vary temp & seed)
python -m commscm.experiments.week5_live_langgraph --stoch-matrix

# Attribution Stability (K reps × tasks)
python -m commscm.experiments.week5_live_langgraph --stability --temperature 0.3
```

---

## Week 6 (preregistered)

See `commscm/WEEK6_PREREGISTRATION.md`.

```
Live trace → CR → one architecture edit → re-run → measure improvement
```

Still no verifier (H3 deferred). No replay/attribution changes.
