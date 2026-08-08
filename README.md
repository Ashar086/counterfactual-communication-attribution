# CommSCM

> **CommSCM is frozen. The remainder of the project is scientific validation, not algorithm development.**  
> From now until submission, every week answers **one scientific question** — not one new feature.  
> **Stop building CommSCM. Start trying to disprove it.**  
> **Standing directive:** Every commit must answer a scientific question or improve reproducibility. No commit should make CommSCM “more clever.”  
> **Paper rule:** Nothing enters the paper unless it appears in [`CLAIMS_LEDGER.md`](commscm/CLAIMS_LEDGER.md).

| Phase | Scientific question | Outcome |
|-------|---------------------|---------|
| **VI.B** | Does CommSCM work on official SWE-bench Verified? | Evidence |
| **VI.C** | Does it generalize to WebArena? | Evidence |
| **VII** | What are the method’s limitations? | Evidence |
| **VIII** | Can independent reviewers reproduce the results? | Evidence |

None of these phases change IF-C-SCM, Communication Responsibility, Replay, or CCAS — unless a completed [`FALSIFICATION_REPORT.md`](commscm/FALSIFICATION_REPORT.md) shows a core assumption is invalid.

**Each week produces exactly one of:** new external evidence · falsification report · paper text · reproducibility improvements.  
**Nothing else** — no new concepts, operators, equations, or governance.

---

## Governance map

| Artifact | Role |
|----------|------|
| [`FREEZE.md`](commscm/FREEZE.md) | Frozen method, evidence ladder, branch policy, advising rules |
| [`CLAIMS_LEDGER.md`](commscm/CLAIMS_LEDGER.md) | Claim ↔ evidence ↔ abstract eligibility |
| [`DECISION_LOG.md`](DECISION_LOG.md) | Dated governance / scope decisions |
| [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) | Env, seeds, commands, digests, expected outputs |
| [`THREATS_TO_VALIDITY.md`](commscm/THREATS_TO_VALIDITY.md) | Living threats log |
| [`FALSIFICATION_REPORT.md`](commscm/FALSIFICATION_REPORT.md) | Required before any core change |
| [`PART_VI_B_PREREGISTRATION.md`](commscm/PART_VI_B_PREREGISTRATION.md) | Official Verified H5 prereg |
| [`PART_VI_B_RESULTS.md`](commscm/PART_VI_B_RESULTS.md) | Official Verified results (after run) |
| [`PART_VI_C_WEBARENA.md`](commscm/PART_VI_C_WEBARENA.md) | WebArena plan |
| [`PAPER_OUTLINE.md`](commscm/PAPER_OUTLINE.md) | Manuscript structure |

Method implementation stays untouched while evidence grows.

---

## Branch policy (strict)

| Branch | Role |
|--------|------|
| `main` / `master` | **Frozen CommSCM** (paper version). No core-algorithm commits during validation. |
| `investigation/*` | Temporary debugging or exploratory work only. |

**Merge into `main`/`master` only if** a filed falsification report under `commscm/falsification_reports/` demonstrates that a core assumption is genuinely invalid. Adapter/harness/eval/paper docs may land on main without a falsification report; **IF-C-SCM / CR / Replay / Attribution / CCAS** may not.

---

## Evidence chain (target narrative)

1. **Formalization** — Defined IF-C-SCM and unified communication responsibility.  
2. **Correctness** — Exact replay oracle validated.  
3. **Efficiency** — Replay engine approximates the oracle with improved scaling.  
4. **Controlled studies** — Communication attribution localizes and repairs failures.  
5. **Framework invariance** — Same frozen method transfers across LangGraph and AutoGen via adapters only.  
6. **Official benchmarks** — Performance evaluated on SWE-bench Verified (and WebArena if completed).  
7. **Limitations** — Clearly documented threats, failures, and unsupported claims.

That tells a coherent scientific story: define → freeze → stress-test — not a continuous stream of new ideas.

---

## Effort allocation (until submission)

~100% on: **VI.B official Verified** · **VI.C WebArena if feasible** · **paper drafting in parallel** · **hostile external review**.

**Next:** Lock and sign Part VI.B → run official evaluation → report honestly (`PART_VI_B_RESULTS.md`).
