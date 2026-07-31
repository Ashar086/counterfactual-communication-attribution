# RESEARCH_LOG.md

## Status

| Part | Status |
|------|--------|
| I — Attribution | ✅ Frozen |
| II — Replay Engine | ✅ Frozen (`v0.3-replay-engine`) |
| III — CCAS (synthetic H1 + H2-lite) | ✅ **Feature-frozen** (`v0.5-ccas-synthetic`) |
| H3 verifier | ⏸ Deferred — do **not** implement next |
| IV — External validity | ▶️ **Week 5 active** |

---

## Claims (defensible wording)

### H1
> CR-guided consistently identifies the causal harmful edge while reward-only does not.

### H2-lite (not full H2)
> Several edit policies can achieve task repair, but only CR-guided consistently repairs via the true harmful communication pathways.

### Benchmark note (paper)
Terminal sink must remain attached; otherwise policies can falsely “repair” by disconnecting the output.

---

## Week 5 — Real LangGraph attribution (no editing)

Plan: `commscm/WEEK5_EXTERNAL_VALIDITY.md`

1. Extract `RunTrace` from LangGraph `AgentState` (`commscm/traces/langgraph_extract.py`)
2. Score with frozen Descendant engine + `langgraph_reward_outcome` (marker-based; no LLM re-roll in the soft-null loop yet)
3. Compare CR vs reward-only vs random P@1 against `poisoned_node` → event map

Runner:
- Offline (default): `python -m commscm.experiments.week5_langgraph_localize`
- Live LLM: `python -m commscm.experiments.week5_langgraph_localize --live`

### Next after Week 5 gate
Week 6: single-edit CCAS on real traces (repair). H3 only if still needed.

---

## Tags
- `v0.3-replay-engine` — Part II
- `v0.4-pre-ccas` — Part III interfaces
- `v0.5-ccas-synthetic` — CCAS feature freeze after H1 + H2-lite
