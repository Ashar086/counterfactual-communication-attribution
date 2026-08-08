# Falsification Report (template)

**Required before any change to:** IF-C-SCM · Communication Responsibility · Replay engine · Attribution algorithm · CCAS operators.

**Branch rule:** do this work on `investigation/*`. Merge to `main`/`master` only after this report is filed under `commscm/falsification_reports/` and approved. See `FREEZE.md` § Branch policy / repo `README.md`.

If this report cannot be completed honestly, **the method stays frozen.** Adapter/harness fixes do **not** need this form.

Copy to `commscm/falsification_reports/YYYY-MM-DD_<short-name>.md` when filing.

---

## Metadata

| Field | Content |
|-------|---------|
| Date | |
| Author | |
| Components proposed for change | IF-C-SCM / CR / Replay / Attribution / CCAS (list) |
| Evidence ladder level that exposed the issue | Official SWE-bench / WebArena / other (name) |
| Linked threats log entry | `THREATS_TO_VALIDITY.md` date/row |

---

## 1. Which benchmark / experiment exposed the issue?

Protocol, artifact paths, metrics. Prefer higher-ladder levels (`FREEZE.md` evidence ladder).

## 2. Which assumption failed?

Map to a concrete assumption (e.g. channel observability, soft-null semantics, single-edit sufficiency, deterministic replay, gold-edge construct).

## 3. Why can't the issue be handled in an adapter or harness?

Show that extractors, mechanisms, evaluation glue, or logging cannot absorb the failure without lying about the method.

## 4. Why is a core change scientifically necessary?

What would remain false or undefined without touching the frozen core? What alternative explanations were ruled out (bug, confound, unfair metric, underspecified harness)?

## 5. Proposed change (minimal)

Describe the smallest core delta. Explicitly list what will **not** change.

## 6. Impact on claims ledger

Which rows in `CLAIMS_LEDGER.md` flip from Supported → Pilot / Unsupported / revised scope? Abstract checkboxes to revoke?

## 7. Decision

| Outcome | Action |
|---------|--------|
| **Insufficient report** | No core change |
| **Adapter-only mitigation** | Fix adapter; log threat; core unchanged |
| **Accepted limitation** | Paper limitation section; core unchanged |
| **Core change approved** | Implement minimal delta; retag; re-run affected ladder levels |

Sign-off: __________________ date: __________
