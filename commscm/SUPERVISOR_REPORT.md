# Supervisor Progress Report — CommSCM / Counterfactual Communication Attribution

**Date:** 4 August 2026  
**Project:** Communication-centric causal attribution for multi-agent failures (CommSCM)  
**Phase:** Main method development complete; paper preparation underway  

---

## 1. Executive summary

We developed and **froze** a communication-event causal attribution framework (IF-C-SCM, counterfactual soft interventions, exact/efficient replay, single-edit CCAS). The method was validated across synthetic, live LangGraph, AutoGen (adapter-only transfer), and SWE-bench–shaped pilots, then evaluated on **official SWE-bench Verified** under a preregistered protocol.

**Main scientific takeaway:** Attribution localizes harmful communication well under our constructs; **official Resolve@1 did not improve** because failures concentrate in **downstream patch synthesis / `git apply`**, not in wrong-edge selection. We do **not** claim an SWE-bench win. WebArena was preregistered but **not executed** due to infrastructure limits (~300+ GB images / no AWS AMI).

The coding/method phase is effectively finished. Remaining work is paper polish, hostile review, and submission.

---

## 2. What was built (frozen)

| Component | Status |
|-----------|--------|
| IF-C-SCM (communication events as causal units) | Frozen |
| Communication Responsibility (CR) via soft interventions | Frozen |
| Exact + efficient replay (descendant / COW) | Frozen |
| CCAS (single prune/weaken edit) | Frozen |
| Governance (preregistration, claims ledger, falsification gate) | In place |

**Operating rule:** No core algorithm changes after freeze unless a formal falsification report requires it. Evidence determines claims.

---

## 3. Evidence obtained

| Level | Result |
|-------|--------|
| Synthetic localization / repair | Strong under controlled poisons |
| Efficient replay | Cost tracks affected subgraph (validated regimes) |
| Live LangGraph | End-to-end localize → edit → re-run |
| AutoGen transfer | Adapter-only; same-task CR rankings agree (Top-1 / Kendall τ = 1.00) |
| SWE-bench Verified–**shaped** pilot | Controlled transfer; not official Docker Resolve@1 |
| **Official SWE-bench Verified (VI.B)** | Closed — see §4 |
| Official WebArena (VI.C) | Preregistered; **not run** (infra) |

---

## 4. Official SWE-bench Verified (Part VI.B) — key numbers

- **Design:** n=100, seed=42, `gpt-4o-mini`, four methods, preregistered analysis  
- **Resolve@1:** **0.00** for CR-guided, reward-only, random, and static  
- **Localization (CR vs reward-only):** gold-edge hit **1.00** vs **~0.33**; proxy repair for CR **~0.97**  
- **Audit (n=20 patch-apply failures):** **20/20** still had correct gold edge + proxy pass; failures were wrong paths / malformed diffs / hunk mismatch  

**Interpretation:** Null Resolve@1 does **not directly falsify** attribution; it shows the end-to-end bottleneck is patch synthesis. We therefore **cannot** claim “CommSCM improves SWE-bench Resolve@1.”

---

## 5. WebArena (Part VI.C)

Preregistered (original WebArena, n=100, seed=42); adapter + fail-closed official runner implemented; offline smoke confirmed adapter/CR compatibility only.

**Not executed:** full official stack requires ~300+ GB of Docker images (or AWS AMI); local free disk ~41 GB; no AWS credentials. Recorded as an **infrastructure limitation**, not a method failure. Protocol remains frozen for future execution.

---

## 6. Paper positioning (locked)

> We introduce a communication-centric causal attribution framework for multi-agent systems, demonstrate efficient counterfactual replay and adapter-level transfer across frameworks, and show that official software-engineering evaluation exposes **downstream patch synthesis—not communication attribution**—as the dominant bottleneck for end-to-end repair.

Claims are gated by a **claims ledger** (Supported / Pilot / Not tested / Unsupported).

---

## 7. Immediate next steps

1. Polish paper (theory, method, figures, CIs, reproducibility package)  
2. Hostile internal review (try to reject the paper)  
3. Submit  
4. Optional later: WebArena when compute exists; oracle-patch control on the SWE path  

**Not planned:** redesigning CR/replay/CCAS, chasing benchmarks with new operators, or months of WebArena hardware acquisition.

---

## 8. Ask for supervisor

Please confirm agreement with (a) freezing the method, (b) the honest SWE-bench / WebArena claim scope, and (c) shifting effort to writing and submission.
