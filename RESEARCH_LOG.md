# RESEARCH_LOG.md

## Status

| Part | Status |
|------|--------|
| I — Attribution | ✅ Frozen (v0.2*) |
| II — Replay Engine | ✅ Frozen (`v0.3-replay-engine`) |
| III — interfaces | ✅ Frozen (`v0.4-pre-ccas`) |
| III — Phase A / H1 | ✅ Gate **PASS** |
| III — Phase B | ✅ Gate **PASS** (single edit apply; no iterative CCAS) |

Foundation rule: touch Parts I–II only if a real-agent experiment forces it.

---

## Week 4

### RQ
> Can communication attribution improve multi-agent architectures more effectively than existing architecture search methods?

### Phase A / H1
| Method | P@1 | R@3 | nDCG@3 | FP@1 |
|--------|----:|----:|-------:|-----:|
| Random | 0.12 | 0.12 | 0.13 | 0.88 |
| Reward-only | 0.00 | 0.00 | 0.00 | 1.00 |
| CR-guided | **1.00** | **0.83** | **1.00** | **0.00** |

### Phase B — single top-1 edit apply
Implementation: `apply_single_edit` / `ArchitectureRegistry.apply_proposal` (edits[0] only).

Suite: chain-fault (unique path E0→…→sink) so a correct single edit can repair the terminal sink.

| Method | repair | hitGold | dY |
|--------|-------:|--------:|---:|
| Random | 1.00 | 0.08 | 1.00 |
| Reward-only | 1.00 | 0.00 | 1.00 |
| CR-guided | **1.00** | **1.00** | 1.00 |

Note: on a chain, cutting *any* edge can repair the terminal sink; **gold-edge hit rate** is the discriminating Phase-B metric. CR-guided always targets E0→E1.

**Phase B gate: PASS**

### Next
- Not yet Phase D (iterative CCAS) — H2/H3 / full baselines still ahead
- Optional: harder multi-path suites before loops

### Pre-registered metrics
See `commscm/WEEK4_PREREGISTRATION.md`

---

## Tags
- `v0.3-replay-engine` — Part II frozen
- `v0.4-pre-ccas` — Part III interfaces + hypotheses/metrics; no CCAS impl at tag time
