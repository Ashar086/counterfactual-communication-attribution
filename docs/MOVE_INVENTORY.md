# Repo cleanup inventory (2026-08-12)

## Root result/artifact files → `results/` (28 files, filenames unchanged)

- `commscm-oracle-gold.oracle_gold_full_n100_lf.json`
- `commscm-oracle-gold.oracle_gold_sample_n10_s7.json`
- `commscm-oracle-gold.oracle_gold_sample_n10_s7_lf.json`
- `commscm-vi-b-cr_guided.cr_guided_sample_n10_s7_lf.json`
- `commscm-vi-b-cr_guided.vi_b_lf_rescore_cr_guided.json`
- `commscm-vi-b-cr_guided.vi_b_rescore_part_vi_b_official_cr_guided.json`
- `commscm-vi-b-random.vi_b_lf_rescore_random.json`
- `commscm-vi-b-random.vi_b_rescore_part_vi_b_official_random.json`
- `commscm-vi-b-reward_only.vi_b_lf_rescore_reward_only.json`
- `commscm-vi-b-reward_only.vi_b_rescore_part_vi_b_official_reward_only.json`
- `commscm-vi-b-static_heuristic.vi_b_lf_rescore_static_heuristic.json`
- `commscm-vi-b-static_heuristic.vi_b_part_vi_b_official_{1..15}.json` (15 files)
- `commscm-vi-b-static_heuristic.vi_b_rescore_part_vi_b_official_static_heuristic.json`
- `gold.vi_b_gold_smoke.json`

## Process/log files → `docs/`

- `DECISION_LOG.md` (from repo root)
- `RESEARCH_LOG.md` (from repo root)
- `CLAIMS_LEDGER.md` (from `commscm/CLAIMS_LEDGER.md`)

## Added

- `LICENSE` (MIT, 2026, Muhammad Ashar Ishfaq and Muhammad Asad Ishfaq)
- Rewritten public `README.md`
- This inventory file

## Path reference updates (not logic)

Scripts/docs that pointed at root JSON paths or old CLAIMS/DECISION/RESEARCH locations were updated to `results/` or `docs/`.
