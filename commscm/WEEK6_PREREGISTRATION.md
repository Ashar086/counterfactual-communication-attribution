# Week 6 — Real repair (single architecture edit)

**Status:** ✅ **Frozen** after balanced live gate PASS. Tag `v0.6-live-repair`. No further Week 6 tuning.

---

## Research question (frozen)

> Can communication attribution improve a real multi-agent system through a **single** architecture edit?

Everything in Week 6 answers **only** this question.

---

## Attribution space vs action space

Week 6 makes an explicit separation (Part IV glue; does not change CR):

| Space | Contents | Role |
|-------|----------|------|
| **Attribution space** | All events, including exogenous/root (e.g. C0 task) | CR may correctly blame a root cause |
| **Action space** | Controllable **agent↔agent** communication edges only | Architecture edits (prune/weaken) |

Exogenous edges such as `C0→C1` may rank high under attribution but are **not** editable architecture pathways.

**Action selection (Part IV, not a CR change):** among CR-ranked prune/weaken edits, prefer
edges whose source is the top-1 attributed event, and among those the consumer
closest to the sink (highest `time_index`). This separates “who is to blame”
from “which controllable wire to cut.”

Claim preserved: *we change the execution environment (live gating), not the attribution algorithm.*

---

## Scope (do not expand)

```
Live multi-agent execution
        ↓
RunTrace
        ↓
AttributionReport
        ↓
Top-1 harmful communication edge
        ↓
One architecture proposal  (prune_edge | weaken_edge only)
        ↓
Re-run identical task
        ↓
Measure outcome difference
```

| Allowed | Forbidden |
|---------|-----------|
| Adapter glue: map prune/weaken → live edge gate | Verifier insertion (H3) |
| Exactly one edit | CCAS search / multi-edit / adaptive policies |
| CR vs reward-only vs random | Replay / attribution algorithm changes |
| Failure taxonomy F1–F6 | Learned surrogates, new CR variants |

---

## Intervention

Exactly one edit per failed run:

- `prune_edge` — consumer does not read that parent artifact
- `weaken_edge` — consumer reads channel soft-null instead

Live apply is **Part IV glue** (`edge_interventions` on `AgentState` + node input gating).  
Do **not** use synthetic rematerialize as the live outcome path.

---

## Primary metrics (pre-registered)

| Metric | Definition |
|--------|------------|
| Task Success Rate | \(P(Y \ge 1)\) before / after |
| Δ Task Success | after − before |
| Gold Edge Hit | edit endpoints incident to gold fault event |
| Edit Precision | among CR edits, fraction hitting gold harmful edges |
| Frac repaired | \(Y_\mathrm{before}<1\) and \(Y_\mathrm{after}\ge 1\) |
| **Repair Attribution Precision** | among successful repairs, fraction that hit a gold harmful edge |

### Secondary

| Metric | Definition |
|--------|------------|
| Token / Latency Δ | after − before (when logged) |
| Number of edits | = 1 by design |
| Attribution Stability | Week 5 appendix (top-1 + Kendall τ) |
| Edit Stability | same CR `(src,tgt,kind)` across repeated runs of same task |
| Failure taxonomy | every unsuccessful repair → exactly one of F1–F6 |

---

## Failure taxonomy (exactly one code)

| Code | Meaning |
|------|---------|
| F1 | Attribution incorrect |
| F2 | Attribution correct, edit ineffective |
| F3 | Edit improves locally but task still fails |
| F4 | Environment stochasticity |
| F5 | Parser / extraction / pipeline issue |
| F6 | Benchmark limitation (unsupported wire, sink invalid, …) |

---

## Success criterion (pre-registered)

A repair counts as **successful** only if **all** hold:

1. Architecture edit is from the evaluated policy (CR-guided for the treat arm)
2. Exactly one edit is applied (`prune_edge` or `weaken_edge`)
3. Task utility improves **or** failure is removed (\(Y_\mathrm{after} > Y_\mathrm{before}\) or \(Y_\mathrm{after}\ge 1\) with prior failure)
4. Sink / output remains structurally valid (executor still receives a code artifact; graph not orphaned)

### Gate

On the live poison suite (failed baselines only):

- CR-guided `frac_repaired` **>** reward-only **and** **>** random
- Pipeline OK rate ≥ 0.9
- Report F1–F6 counts (do not hide failures)

---

## Evidence chain (if Week 6 succeeds)

```
IF-C-SCM → CR → Efficient Replay → Real Trace Localization
        → Single Architecture Edit → Improved Real-Agent Performance
```

---

## Schedule note

Methods and poison modes must be **independent** (balanced blocks).  
An early pilot confounded them (CR only saw planner poison); archived at
`results/week6_live_repair_confounded_schedule.json`. Paper results use the balanced run only.

---

## After Week 6 (not now)

Second framework or public bench; baselines (GPTSwarm, AgentPrune, G-Designer, MaAS); harder fault taxonomy.
