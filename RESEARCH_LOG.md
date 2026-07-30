# RESEARCH_LOG.md

## Status

| Part | Status |
|------|--------|
| I — Attribution | ✅ Frozen (v0.2*) |
| II — Replay Engine | ✅ Frozen (`v0.3-replay-engine`) |
| III — interfaces | ✅ Frozen (`v0.4-pre-ccas`) |
| III — Phase A / H1 | ✅ Gate **PASS** (proposal-only; no iterative CCAS yet) |

Foundation rule: touch Parts I–II only if a real-agent experiment forces it.

---

## Week 4

### RQ
> Can communication attribution improve multi-agent architectures more effectively than existing architecture search methods?

### Phase A / H1 (done)
Ranked `ArchitectureProposal` only — no graph mutation, no iterative CCAS.

| Method | P@1 | R@3 | nDCG@3 | FP@1 |
|--------|----:|----:|-------:|-----:|
| Random | 0.12 | 0.12 | 0.13 | 0.88 |
| Reward-only (no FAULT_ leakage) | 0.00 | 0.00 | 0.00 | 1.00 |
| CR-guided | **1.00** | **0.83** | **1.00** | **0.00** |

**H1 gate: PASS** — CR-guided strictly beats reward-only and random on pre-registered edge-localization metrics.

Note: an earlier reward-only variant that inspected `FAULT_` markers tied CR at P@1=1.0 (label leakage). Pre-registration forbids that; baseline must not read fault labels.

### Next (only because H1 passed)
- Phase B: single architecture edit apply
- Not yet: iterative CCAS / H2 / H3 / full baselines (GPTSwarm, …)

### Pre-registered metrics
See `commscm/WEEK4_PREREGISTRATION.md` (H1–H3 metric tables locked).

---

## Tags
- `v0.3-replay-engine` — Part II frozen
- `v0.4-pre-ccas` — Part III interfaces + hypotheses/metrics; **no** CCAS impl at tag time
