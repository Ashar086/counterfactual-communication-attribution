# Part VI — SWE-bench Verified–Shaped Pilot

## Immediate priority (advising lock)

1. **No new internal / shaped / synthetic benches** unless an official bench exposes a concrete gap.  
2. Finish **Part VI.B preregistration** (below) → run exactly as written → report honestly.  
3. Failures → falsification report before any core change.  
4. Parallel: draft frozen paper sections (`PAPER_OUTLINE.md`).

Governance: `FREEZE.md` § Advising rules.

| Phase | Name | Status |
|-------|------|--------|
| **Part VI** | SWE-bench Verified–**Shaped** Pilot | ✅ Stages 1–4 PASS |
| **Part VI.B** | Official SWE-bench Verified (Docker `resolve@1`) | ✅ **CLOSED** — process PASS / partial (Resolve@1=0; localization holds; do not rerun) |
| **Part VI.C** | Official WebArena | ⛔ **Preregistered, not executed** (infra); protocol frozen for later |

**Not** “improve SWE-bench.” Treat CommSCM as a **frozen hypothesis** and try to falsify it.

**Part VI (shaped) question:**

> Does the frozen CommSCM pipeline remain effective on a SWE-bench-inspired controlled task distribution under communication poisons, via adapter-only transfer?

**Part VI.B question (official):**

> Does the frozen CommSCM pipeline remain effective on established community benchmarks (official harness)?

Parts I–V frozen. Adapter / harness only. See `FREEZE.md` (claims matrix) and `STATUS_AFTER_PART_V.md`.

---

## Core Invariance Principle (Part VI / VI.B)

Preregistered success requires **all** of:

1. **No core algorithm modifications** throughout Part VI / VI.B.  
2. **All benchmark-specific logic** isolated to adapters and evaluation harnesses.  
3. **Any** required change to IF-C-SCM, CR, Replay, or CCAS is recorded **first** as a falsification / threat in `THREATS_TO_VALIDITY.md` before it is considered as a future extension.

“Just one small tweak” to the core = **failed** external-validity transfer for that experiment.

---

## Planned order

| Order | Benchmark | Role |
|-------|-----------|------|
| 1 | **SWE-bench Verified–shaped pilot** (Part VI) | ✅ Done — controlled transfer |
| 2 | **Official SWE-bench Verified** (Part VI.B) | Primary external-validity gate |
| 3 | **WebArena** (Part VI.C) | Secondary |

Subset evaluation is acceptable if scoped honestly; reviewers prefer recognized benches over another custom suite.

---

## Stages (Part VI shaped — executed)

### Stage 1 — Trace extraction

```
SWE-bench Verified problem statements (shaped harness)
        ↓
RunTrace
```

Success: zero changes to IF-C-SCM, replay, CR, CCAS. Benchmark logic only in adapter/harness.

### Stage 2 — Attribution (no repair)

| Metric |
|--------|
| Gold Edge Hit (when gold exists) |
| P@1 |
| MRR |
| Attribution Stability |

### Stage 3 — Single repair

```
Trace → CR → Single prune/weaken → Re-run → Evaluate
```

No verifier insertion. No iterative CCAS. No new operators.

### Stage 4 — Baselines (same single-edit budget)

| Baseline | Applied? |
|----------|----------|
| Random | ✅ |
| Reward-only | ✅ |
| Static heuristic | ✅ |
| Architecture-search (GPTSwarm, AgentPrune, G-Designer, MaAS) | ❌ Skipped — unfair vs single prune/weaken on fixed C0–C5 |

Defend as: *baselines operating under the same single-edit action budget.*

---

## Decision rules

| Outcome | Action |
|---------|--------|
| **PASS (shaped)** | Controlled transfer holds → document as pilot; proceed to **Part VI.B** |
| **PASS (VI.B official)** | Frozen method transfers without core modifications → substantially stronger external validity |
| **FAIL** | Do **not** immediately modify CommSCM. Document: Which assumption failed? Prefer a **limitation section** over an ad hoc fix |

Negative / limited results are valuable if characterized.

---

## Evidence chain

```
Theory
   ↓
Synthetic validation
   ↓
Replay scaling
   ↓
Live LangGraph
   ↓
Framework invariance (LangGraph ↔ AutoGen)
   ↓
SWE-bench–inspired controlled pilot   ← Part VI ✅
   ↓
Official SWE-bench Verified           ← Part VI.B ⏳
   ↓
Official WebArena                     ← Part VI.C ⏳
   ↓
Paper
```

---

## What Part VI (shaped) is not

| Not the goal |
|--------------|
| Claiming official SWE-bench Verified / leaderboard results |
| Improving SWE-bench agent performance as a product |
| Chasing SOTA via method tweaks |
| Adding verifiers / new CCAS operators to pass the bench |
| Claiming superiority vs architecture-search methods |

---

## Claims after shaped PASS (conservative)

May claim: *frozen CommSCM remains effective on a SWE-bench-inspired controlled evaluation via adapter-only transfer; CR-guided edits beat same-budget baselines.*

Must still **not** claim: official Verified resolve rates, universal independence, theoretical optimality, verifier effectiveness, or SOTA.

Full matrix: `FREEZE.md` § Claims matrix.

---

## SWE-bench Verified–shaped execution scope (honest)

| In scope | Out of scope (logged) |
|----------|------------------------|
| HF `princeton-nlp/SWE-bench_Verified` problem statements | Official Docker `resolve@1` harness |
| Isomorphic C0–C5 multi-agent + communication poisons | Claiming SWE-bench leaderboard / SOTA |
| Adapter → RunTrace → frozen CR / single prune-weaken | Core IF-C-SCM / CR / replay / CCAS edits |
| Patch-shaped reward proxy (fault markers + artifact shape) | Full FAIL_TO_PASS test execution in containers |

Package: `commscm/adapters/swebench/`  
Experiments: `part_vi_stage{1,2,3,4}_*` · overnight: `part_vi_overnight_runner.py`

---

## Results log (Part VI shaped)

| Stage | Artifact | Gate / key metrics |
|-------|----------|-------------------|
| 1 Trace | `results/part_vi_stage1_swebench_smoke.json` | ✅ CR hit gold (`sphinx-doc__sphinx-9602`) |
| 2 Attribution | `results/part_vi_stage2_swebench_attr.json` | ✅ n=24 CR P@1=1.00 MRR=1.00 Gold Hit=1.00; reward≈0 random≈0.13; stability Kendall τ=1.00 / top-1=1.00 |
| 3 Repair | `results/part_vi_stage3_swebench_repair.json` | ✅ n=14 CR repaired=1.00 Gold Edge Hit=1.00 RAP=1.00 |
| 4 Baselines | `results/part_vi_stage4_swebench_baselines.json` | ✅ CR repaired=1.00 / gold-hit=1.00 vs reward 0.38 / random 0.14 / static 0.50; arch-search skipped (unfair) |

**Verdict (SWE-bench Verified–shaped pilot):** PASS under Core Invariance Principle (adapter-only).  
Treat as **pilot** evidence (small n; absolute rates near 1.00). **Not** official Docker resolve@1 or SOTA.

Harness notes logged in `THREATS_TO_VALIDITY.md`: no gold_patch prune fallback; C4→C5 sink detach excluded from Stage 3–4 action space.

---

## Part VI.B — Official SWE-bench Verified

**Authoritative preregistration:** [`PART_VI_B_PREREGISTRATION.md`](PART_VI_B_PREREGISTRATION.md) (H5).

| Requirement | Detail |
|-------------|--------|
| Harness | Official Docker / community `resolve@1` |
| Core | Frozen — adapter/harness only; falsification report before any core change |
| Reporting | Never conflate with Part VI shaped pilot metrics |
| Ladder | Completing VI.B does **not** reopen Levels 1–5 unless VI.B falsifies them |
| Run gate | Signature block in prereg must be complete before Docker eval |

Do **not** start official evaluation until all `UNLOCKED` fields in the prereg are filled and signed.

**Rule:** If results miss the pre-registered PASS gate, prefer a limitation section / falsification report over changing the frozen method.

---

## Related

- Claims matrix: `commscm/FREEZE.md`  
- Part VI.B prereg (H5): `commscm/PART_VI_B_PREREGISTRATION.md`  
- Status: `commscm/STATUS_AFTER_PART_V.md`  
- Threats: `commscm/THREATS_TO_VALIDITY.md`  
- Part V: `commscm/PART_V_FRAMEWORK_INVARIANCE.md`
- Paper outline: `commscm/PAPER_OUTLINE.md`
