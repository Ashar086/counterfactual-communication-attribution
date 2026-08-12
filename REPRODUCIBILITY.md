# CommSCM — Reproducibility

**Purpose:** Make reproduction effortless from a clean checkout. This is not method documentation — it is an experimental record.  
**Rule:** Every validated experiment must have a row (or subsection) here before it is cited in the paper.  
**Governance:** `FREEZE.md` · [`docs/CLAIMS_LEDGER.md`](docs/CLAIMS_LEDGER.md) · `PART_VI_B_PREREGISTRATION.md`

Update this file when locking VI.B / VI.C runs. Prefer **pinned versions and digests** over floating `>=` ranges for paper-facing runs.

---

## Weekly deliverable rule

From now until submission, each week produces **one** of:

1. A new validated experiment  
2. A falsification report  
3. A paper section  
4. A reproducibility improvement  

**Not:** new replay algorithms · new attribution methods · new CCAS operators · new theory (unless falsified).

---

## Environment setup (base)

| Item | Value |
|------|--------|
| OS (dev machine example) | Windows 10 / record as used for each run |
| Python | Record exact: `python --version` → ___ (example checkout had 3.14.2; pin a paper Python, e.g. 3.11.x, if preferred) |
| Package lock | `requirements.txt` (looseness: ranges). **Paper runs:** freeze a `requirements-lock.txt` or `uv.lock` / `pip freeze` artifact at experiment tag |
| Install | `python -m venv .venv` then `pip install -r requirements.txt` (+ adapter extras below) |
| API keys | `OPENAI_API_KEY` (or provider used) via env; never commit secrets |
| Repo root | Working directory for all `python -m commscm...` commands |

### Core Python deps (`requirements.txt`)

```
langgraph>=0.2.0
langchain-core>=0.3.0
pydantic>=2.0.0
openai>=1.40.0
```

### Adapter / benchmark extras (install when reproducing that track)

| Track | Extra packages / notes |
|-------|------------------------|
| AutoGen (Part V) | AutoGen AgentChat stack as used in `commscm/adapters/autogen/` — pin versions when locking paper run |
| SWE-bench shaped / official | `datasets` (HF); official VI.B also needs SWE-bench Docker harness — pin harness commit + image digest in VI.B lock sheet |
| WebArena (VI.C) | TBD in `PART_VI_C_WEBARENA.md` |

---

## Hardware & seeds (defaults)

| Item | Record per experiment |
|------|------------------------|
| Hardware | CPU/GPU/RAM or cloud SKU |
| Selection / RNG seeds | e.g. instance selection `seed=42` in Part VI shaped loaders |
| Model temperature | Live LangGraph often `0.0`; stability runs used `0.3` — see experiment rows |
| Docker | N/A until Part VI.B official; then image **digest** mandatory |

---

## Experiment catalog

Fill **Commit/tag**, **Runtime**, **Hardware**, **Model** when locking paper-facing reproductions. Commands assume repo root.

### Part II / Week 3 — Replay efficiency

| Field | Value |
|-------|--------|
| Question | Does efficient replay match oracle under sparse interventions? |
| Commands | `python -m commscm.experiments.week3_descendant_ratio` · `week3_approximation` · `week3_cost_profile` · grids as in `REPLAY_ENGINE_GUARANTEES.md` |
| Expected outputs | `results/week3_*.json`, `results/week3_5/` |
| Commit/tag | `v0.3-replay-engine` (historical); re-run on frozen HEAD for paper |
| Expected runtime | ___ |
| Model/API | N/A (synthetic mechanisms) |

### Week 4 — CCAS / H1

| Field | Value |
|-------|--------|
| Commands | See `WEEK4_PREREGISTRATION.md` |
| Expected outputs | `results/week4_h1.json`, `week4_phase_b.json`, `week4_phase_d.json` |
| Commit/tag | `v0.5-ccas-synthetic` |
| Runtime / hardware / model | ___ |

### Week 5 — Live LangGraph localization

| Field | Value |
|-------|--------|
| Commands | `python -m commscm.experiments.week5_live_langgraph --n-runs 102 --temperature 0.0` |
| Stoch matrix | `python -m commscm.experiments.week5_live_langgraph --stoch-matrix --out results/week5_live_stoch_matrix.json` |
| Stability | `python -m commscm.experiments.week5_live_langgraph --stability --stability-reps 5 --temperature 0.3` |
| Expected outputs | `results/week5_live_langgraph.json`, `week5_live_stoch_matrix.json`, `week5_attribution_stability.json` |
| Commit/tag | toward `v0.6-live-repair` |
| Runtime / hardware / model | ___ |

### Week 6 — Live single-edit repair

| Field | Value |
|-------|--------|
| Commands | See `WEEK6_PREREGISTRATION.md` / `python -m commscm.experiments.week6_live_repair` |
| Expected outputs | `results/week6_live_repair.json` |
| Commit/tag | `v0.6-live-repair` |
| Runtime / hardware / model | ___ |

### Part V — Framework invariance (AutoGen)

| Field | Value |
|-------|--------|
| Commands | `python -m commscm.experiments.part_v_stage1_smoke` · `part_v_stage2_autogen_attr` · `part_v_stage3_framework_compare` · `part_v_stage4_autogen_repair` |
| Expected outputs | `results/part_v_stage{1,2,3,4}_*.json` |
| Commit/tag | ___ (record at paper freeze) |
| Runtime / hardware / model | ___ |

### Part VI — SWE-bench Verified–shaped pilot

| Field | Value |
|-------|--------|
| Commands | `python -m commscm.experiments.part_vi_stage1_swebench_smoke` · `part_vi_stage2_swebench_attr` · `part_vi_stage3_swebench_repair` · `part_vi_stage4_swebench_baselines` |
| Overnight | `python -m commscm.experiments.part_vi_overnight_runner` |
| Expected outputs | `results/part_vi_stage{1,2,3,4}_swebench_*.json` |
| Seeds | Instance load `seed=42` (see `commscm/adapters/swebench/load.py`) |
| Commit/tag | ___ |
| Runtime / hardware / model | ___ |
| Scope | **Not** official Docker `resolve@1` |

### Part VI.B — Official SWE-bench Verified

| Field | Value |
|-------|--------|
| Status | **Prereg signed 2026-08-02** (`PART_VI_B_PREREGISTRATION.md`) |
| Results write-up | `PART_VI_B_RESULTS.md` (after run) |
| n / seed / procedure | **100** · seed **42** · full Verified `test` shuffle then first 100 (**no** easy preference) |
| Instance list | `results/part_vi_b_instance_list.json` |
| Dataset | `princeton-nlp/SWE-bench_Verified` |
| Harness | `SWE-bench/SWE-bench@f7bbbb2ccdf479001d6467c9e34af59e44a840f9` |
| Docker | namespace `swebench`; digests → `results/part_vi_b_docker_digests.json` at pull |
| Model | `gpt-4o-mini` · temp **0.0** · top_p **1.0** · max_tokens **4096** |
| API package | `openai==2.51.0` (snapshot: `results/part_vi_b_pip_freeze.txt`) |
| Timeouts | LLM 120s · task 30min · Docker eval 1800s |
| Prompt hash | `results/part_vi_b_prompt_hashes.json` (sha256 of `commscm/adapters/swebench/pipeline.py`) |
| Repro caveat | `part_vi_b_pip_freeze.txt` is a **post-hoc** environment snapshot regenerated from an environment matching pinned versions (`openai==2.51.0`, SWE-bench @ `f7bbbb2…`), **not** the literal `pip freeze` from the original VI.B run (that output was not persisted). Prompt hashes are an exact reconstruction verified against `pipeline.py`. |
| Core baseline commit | `3cc07f6a935f9aee819064ef37d26918998363ae` |
| Tag | `vi-b-prereg-2026-08-02` |
| Expected outputs | `results/part_vi_b_*.json` |
| Commands | `python -m commscm.experiments.part_vi_b_official_runner --out results/part_vi_b_official.json` · analyze: `python -m commscm.experiments.part_vi_b_analyze` |
| Expected runtime | ~hours–days (100×4 LLM + Docker); resume supported via existing `--out` |
| Smoke | LLM: `--limit 1 --skip-docker` → `results/part_vi_b_official_smoke.json` · Gold Docker: `run_evaluation --predictions_path gold --instance_ids django__django-14672 --run_id vi_b_gold_smoke` |

### Part VI.C — WebArena

| Field | Value |
|-------|--------|
| Plan | `PART_VI_C_WEBARENA.md` |
| Prereg | `PART_VI_C_PREREGISTRATION.md` (**EXPERIMENT FROZEN** 2026-08-04) |
| Benchmark | Original WebArena · `web-arena-x/webarena@dce04686a56253aefba7b18a4fa0937cf1dc987b` |
| n / seed | **100** / **42** · `results/part_vi_c_instance_list.json` |
| Model | `gpt-4o-mini` · temp 0.0 · top_p 1.0 · max_tokens 4096 |
| Tag | `vi-c-prereg-2026-08-04` |
| Commands / outputs | Smoke: `python -m commscm.experiments.part_vi_c_smoke` → `results/part_vi_c_smoke.json`, `results/part_vi_c_prompt_hashes.json`. Full n=100 runner TBD. |

---

## Expected output checksum discipline (optional but preferred)

For paper-facing runs, record `sha256` of primary JSON artifacts next to the experiment row or in `results/MANIFEST.json`.

---

## Clean-checkout smoke test

```text
git checkout <paper-tag>
python -m venv .venv
# activate venv
pip install -r requirements.txt   # or requirements-lock.txt when created
python -m commscm.experiments.part_v_stage1_smoke
# expect: results/part_v_stage1_smoke.json ; exit 0
```

Official VI.B smoke requires Docker + signed prereg — do not claim clean-checkout VI.B until those are locked here.

---

## Associated tags (historical)

| Tag | Milestone |
|-----|-----------|
| `v0.3-replay-engine` | Part II |
| `v0.5-ccas-synthetic` | Part III CCAS freeze |
| `v0.6-live-repair` | Part IV LangGraph live repair |

Paper submission tag (create after VI.B): ___
