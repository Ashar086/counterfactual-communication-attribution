# Part VI.C — WebArena Results

**Status:** **Preregistered, not executed** (infrastructure constraint).  
**Prereg:** [`PART_VI_C_PREREGISTRATION.md`](PART_VI_C_PREREGISTRATION.md) — Experiment Frozen 2026-08-04.  
**Decision:** Do **not** spend months chasing hardware. Protocol remains frozen for future execution when capacity exists.

---

## Why not run

| Requirement | Available |
|-------------|-----------|
| Official site images (compressed) | ~304 GB |
| Local free disk (C: + D:) | ~41 GB each |
| AWS AMI `ami-08a862bf98e3bd7aa` | No AWS CLI / credentials on this host |

This is an **infrastructure constraint**, not a method failure and not a falsification of CommSCM.

---

## What was completed before the block

| Artifact | Role |
|----------|------|
| Preregistration (Benchmark A, n=100, seed=42) | Frozen protocol |
| `results/part_vi_c_instance_list.json` | Locked task IDs |
| `commscm/adapters/webarena/` | Adapter → `RunTrace` |
| Offline smoke | Adapter + CR compatibility only |
| `part_vi_c_official_runner` | Fails closed without live env |
| `results/part_vi_c_env_status.json` | Capacity / readiness record |
| `WEBARENA_BRINGUP.md` | AMI / disk bring-up path |

---

## Claims

| Claim | Status |
|-------|--------|
| WebArena adapter smoke (offline) | Supported (Methods/appendix only) |
| Official WebArena H6a/H6b | **Not tested** — do not claim |
| “Method failed on WebArena” | **Unsupported** — experiment not run |

**Paper wording (locked):**  
*We preregistered an official WebArena evaluation (n=100), implemented the adapter and official runner, but could not execute the full benchmark because required infrastructure exceeded available resources. The protocol remains frozen for future execution.*

---

## Core CommSCM

Unchanged. No falsification report. No redesign triggered by this limitation.

**Next project focus:** paper polish (theory, figures, CIs, repro package, hostile review) — not hardware acquisition for VI.C.
