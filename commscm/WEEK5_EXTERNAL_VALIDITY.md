# Week 5 — External validity (attribution on real agent traces)

**Status:** CCAS feature freeze. No H3. No new edit kinds. No algorithm changes unless a real-agent experiment forces them.

**Depends on:** Parts I–II frozen; Part III H1 + H2-lite on synthetic only (`v0.5-ccas-synthetic`).

---

## What is frozen (do not expand)

| Item | Status |
|------|--------|
| IF-C-SCM / CR / soft interventions | Frozen |
| Replay engine (Descendant + COW) | Frozen |
| CCAS propose / single-edit / iterative prune loop | **Feature-frozen** |
| H3 verifier insertion | **Deferred** |

---

## Scientific claims (careful wording)

### H1 (synthetic) — keep
> CR-guided consistently identifies the causal harmful edge while reward-only does not.

Not: “P@1 = 1.0 proves the method.”

### H2-lite (synthetic) — keep, do not overclaim as full H2
> Several edit policies can achieve task repair, but only CR-guided consistently repairs via the true harmful communication pathways.

Not: “CR is better at architecture optimization in general.”

### Benchmark pathology (paper note)
The terminal sink must remain attached; otherwise policies can “repair” by disconnecting the output. Document this explicitly.

---

## Week 5 research question

> On **real** multi-agent traces, does Communication Responsibility localize injected (or labeled) harmful communication events better than reward-only / random ranking?

**Scope this week:**
1. Extract CommSCM `RunTrace` from real LangGraph runs (workshop pipeline).
2. Run **attribution only** (no editing).
3. Measure localization (P@1, MRR, Recall@k) against `poisoned_node` / gold event ids.

**Out of scope this week:** CCAS edits, verifier insertion, SWE-bench/WebArena (Week 6+), AutoGen/CrewAI extractors (next after LangGraph works).

---

## Success criteria (pre-registered)

| Metric | Target (LangGraph poisoned suite) |
|--------|-----------------------------------|
| P@1 vs gold poisoned event | Report; aim ≥ 0.8 on channel-native poisons |
| CR vs reward-only / random | CR strictly better P@1 |
| Algorithm changes | **Zero** unless extractor/outcome mismatch forces a schema-compatible fix |

---

## Roadmap (locked)

| Week | Goal |
|------|------|
| **5** | Real LangGraph traces → attribution → localization (no editing) |
| **6** | Single-edit CCAS on real traces → measure repair |
| **7** | H3 verifier **only if** still needed after Week 6 |
| later | AutoGen / CrewAI / SWE-bench Verified / WebArena / AgentDojo + full baselines |

---

## Foundation rule (unchanged)

> Did a real-agent experiment force this change?

If no → do not touch Parts I–III algorithms.
