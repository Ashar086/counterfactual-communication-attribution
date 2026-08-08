# Falsification Report — CLEAR-FAIL branch (drafted cold, before final VI.B outcome)

**Status:** Pre-drafted for Part VI.B **clear fail** path only.  
**Rule:** Fill sections 1–4 from evidence **after** choosing the clear-fail decision path. Do not invent a core change to “save” the paper.  
**Branch:** File under `investigation/*` if a core change is later approved; otherwise keep as limitation.

Copy to `commscm/falsification_reports/YYYY-MM-DD_vi_b_clear_fail.md` when filing for real.

---

## Metadata

| Field | Content |
|-------|---------|
| Date | _(fill when filing)_ |
| Author | |
| Components proposed for change | □ none yet · □ IF-C-SCM · □ CR · □ Replay · □ Attribution · □ CCAS |
| Evidence ladder level that exposed the issue | Official SWE-bench Verified (Part VI.B) |
| Linked threats log entry | `THREATS_TO_VALIDITY.md` (E1–E7; gold-smoke E6; harness last-wins note) |
| Prereg decision path | **Clearly fails** (`PART_VI_B_PREREGISTRATION.md`) |

---

## Pre-registered triggers for this branch (do not re-litigate)

File this report when **any** of:

- **F0** Core algorithm modification required to proceed  
- **F1** Adapter cannot faithfully extract `RunTrace` for the official setting  
- **F2** Protocol drift / cannot execute as signed without core change  
- **F3** Reproducibility failure beyond locked tolerance  
- **F4** Cannot report the preregistered statistical plan  

**Not** automatic clear-fail (these are limitations / partial success by default):

- Modest or null Resolve@1 vs reward-only  
- Patch-apply failures from agent patch quality  
- Docker/harness environment issues (E6) if adapter/harness can still score and report  
- Weaker results than shaped pilot  

---

## 1. Which benchmark / experiment exposed the issue?

_(Fill after clear-fail is declared.)_

- Protocol: Part VI.B official Verified · n=100 · seed 42 · `gpt-4o-mini` · four same-budget methods  
- Artifacts: `results/part_vi_b_official.json` · `results/part_vi_b_analysis.json` · harness reports · `PART_VI_B_RESULTS.md`  
- Metric that failed the **integrity** bar (not the score exam): ________________  

---

## 2. Which assumption failed?

Check the **smallest** failed assumption (one primary):

| Assumption | Failed? | Notes |
|------------|---------|-------|
| Official tasks expose communication events sufficient for CR | □ | |
| Soft-null / single prune-weaken can change official resolve | □ | |
| Adapter `RunTrace` faithfully represents SWE-bench agent communication | □ | |
| Gold-edge construct remains meaningful under official resolve@1 | □ | |
| Deterministic replay / CR ranking stable enough under temp=0 | □ | |
| Other: ________________ | □ | |

---

## 3. Why can't the issue be handled in an adapter or harness?

Must answer **yes** to reopen core. If any answer is “adapter can fix,” stop — do **not** change IF-C-SCM/CR/Replay/CCAS.

| Question | Answer |
|----------|--------|
| Is this a predictions-file / Docker worker / path-normalize bug? | |
| Is this missing channels in extract.py? | |
| Is this unfair metric or construct mismatch (poison gold vs resolve)? | |
| Can a limitation section absorb it without lying? | |

If adapter/harness/limitation suffices → Outcome = **Adapter-only mitigation** or **Accepted limitation**. Core stays frozen.

---

## 4. Why is a core change scientifically necessary?

Only if §3 shows adapter/harness cannot absorb the failure:

- What remains false without a core change?  
- Alternatives ruled out (bug, confound, E6 harness, underspecified prompt, patch format)?  
- Minimal core hypothesis to revise (one sentence):  

---

## 5. Proposed change (minimal)

| Allowed | Forbidden in this filing unless justified |
|---------|-------------------------------------------|
| Adapter extract / patch normalize / Docker wiring | New CCAS operators |
| Honest limitation + ledger downgrade | New CR definition |
| Documented post-hoc re-eval labeled non-primary | Silent threshold tuning |

Proposed core delta (if any): **None / describe**  
Will **not** change: ________________  

---

## 6. Impact on claims ledger

Before any core patch, mark:

| Ledger row | New status |
|------------|------------|
| Official SWE-bench Verified effectiveness (H5) | Unsupported / Pilot / revised scope: ___ |
| Abstract eligibility for official Verified | ❌ |
| Other rows affected | |

---

## 7. Decision

| Outcome | Action |
|---------|--------|
| **Insufficient report** | No core change |
| **Adapter-only mitigation** | Fix harness/adapter; log threat; core unchanged |
| **Accepted limitation** | Paper limitations; ledger update; core unchanged |
| **Core change approved** | Minimal delta on `investigation/*` + retag + re-run affected ladder |

**Default recommendation when drafting cold:** prefer **Accepted limitation** or **Adapter-only mitigation** over core change unless §3–4 are airtight.

Sign-off: __________________ date: __________

---

## Appendix — known VI.B harness integrity issues (not automatic falsification of CommSCM)

Documented 2026-08-02 during run (wiring, not theory):

1. SWE-bench `run_evaluation` builds `predictions = {instance_id: pred}` → **last method wins** when multiple methods share a jsonl.  
2. Early Docker batches therefore scored almost only **`static_heuristic`**, with many patch-apply errors.  
3. That does **not** by itself falsify IF-C-SCM/CR; it falsifies the **measurement** until per-method eval is used.

Fix: per-method prediction files + optional `max_workers>1` (prereg does not lock worker count). Label any re-score of already-produced patches as harness correction, not a new experimental condition.
