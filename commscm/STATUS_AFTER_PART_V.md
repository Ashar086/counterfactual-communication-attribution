# Current Project Status (After Part VI.B)

**Phase:** Evidence accumulation — falsify / validate the frozen artifact; not algorithm development.  
**Philosophy:** Protect the frozen method. Let the evidence determine the claims.  
**Reviewer question:** *What can we defend?* — not *Did it pass?*

Canonical claims: **`FREEZE.md`** · **`docs/CLAIMS_LEDGER.md`** · Core change gate: **`FALSIFICATION_REPORT.md`**

### Macro phases

| Phase | Status |
|-------|--------|
| I Theory | âœ… Frozen |
| II Efficient Attribution | âœ… Frozen |
| III Architecture Optimization | âœ… Frozen |
| IV External Validation (LG + AutoGen + shaped pilot) | âœ… Frozen |
| V Scientific Validation (official benches + paper) | ðŸš§ Current — VI.B âœ… closed; VI.C next |

---

## What is established

| Contribution | Evidence |
|--------------|----------|
| Communication events as causal unit (not agents) | IF-C-SCM |
| Counterfactual communication attribution (soft interventions) | Unified CR |
| Efficient replay (theory + empirics) | Exact / Descendant / COW |
| Framework invariance (adapter-only LG → AutoGen) | Part V |
| Controlled localization + repair attribution | Weeks 4–6; Parts V–VI shaped; VI.B gold-edge |

## What is not established (claims removed)

| Claim | Status |
|-------|--------|
| Improves official SWE-bench Resolve@1 | âŒ Unsupported (VI.B = 0.00 all methods) |
| Communication edits → repository-valid patches | âŒ Not shown (patch apply dominates failures) |
| Universally effective across arbitrary agent systems | âŒ Unsupported |

---

## Evidence chain

```
Synthetic Bench                         âœ…
        â†“
Replay Scaling                          âœ…
        â†“
Live LangGraph                          âœ…
        â†“
Framework Invariance (AutoGen)          âœ…
        â†“
SWE-bench–inspired controlled pilot     âœ… Part VI
        â†“
Official SWE-bench Verified             âœ… Part VI.B CLOSED (partial success)
        â†“
Official WebArena                           â›” VI.C preregistered, not executed (infra)
        â†“
Hostile review → paper → submit
```

---

## Part VI.B — CLOSED

**Do not rerun** because numbers are disliked. Touch only for a confirmed reproducibility bug.

| Deliverable | Artifact |
|-------------|----------|
| Final Resolve@1 | 0.00 all methods (`part_vi_b_analysis.json`) |
| 95% CIs + effect sizes | same |
| Failure / outcome mix | `PART_VI_B_RESULTS.md` |
| Patch-apply analysis | `part_vi_b_patch_apply_audit.json` |
| Threats | `THREATS_TO_VALIDITY.md` |
| Final interpretation | `PART_VI_B_RESULTS.md` · ledger · decision log |

**Verdict:** Process PASS / partially succeeds. Localization supported; Resolve@1 win unsupported. Null Resolve@1 does **not directly** falsify attribution (failures at patch apply). Largest remaining *SWE* gap: oracle-patch control (after WebArena).

---

## Remaining roadmap (priority order)

| # | Work | Rule |
|---|------|------|
| 1 | **Paper writing / polish** | Theory, method, figures, CIs, repro; claims âŠ† ledger |
| 2 | **Hostile Reviewer #2** | Try to reject the paper |
| 3 | **Submission** | Honest VI.C limitation; no invented WebArena results |
| 4 | **VI.C (future)** | Preregistered-not-executed; run only when AMI/~400GB exists |
| 5 | **Oracle-patch (optional)** | After/ beside paper if capacity; before any new algorithm |

### Do NOT

Chase WebArena hardware for months · invent verifier insertion · redesign CR/replay · tune to chase benches · claim WebArena generalization from smoke.

Every hour from here should increase **credibility of the write-up and evidence package**, not algorithm complexity or infra theater.

---

## Paper positioning (locked)

> We introduce a communication-centric causal attribution framework for multi-agent systems, demonstrate efficient counterfactual replay and adapter-level transfer across frameworks, and show that official software-engineering evaluation exposes downstream patch synthesis—not communication attribution—as the dominant bottleneck for end-to-end repair.

Not: “We outperform SWE-bench.”

---

## Related

- Freeze / claims: `FREEZE.md` · `docs/CLAIMS_LEDGER.md`  
- VI.B: `PART_VI_B_RESULTS.md` · `PART_VI_B_PREREGISTRATION.md`  
- VI.C: `PART_VI_C_WEBARENA.md`  
- Threats: `THREATS_TO_VALIDITY.md` · Decision log: `docs/DECISION_LOG.md`  
- Paper: `PAPER_OUTLINE.md`
