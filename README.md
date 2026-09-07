# CommSCM — Counterfactual Communication Attribution

**CommSCM** is a communication-centric causal framework for multi-agent LLM systems. It treats typed communication events as the units of attribution, scores them with Communication Responsibility (CR) via soft interventions and counterfactual replay, and applies at most one architecture edit (prune or weaken an edge) under CCAS. Framework-specific logic lives in adapters; the core method is held fixed across settings.

## Paper

This repository is the code, logs, and results companion to:

> **Counterfactual Communication Attribution: Localizing Failures in Multi-Agent LLM Systems**  

## Key results (summary)

- Across synthetic oracles, live LangGraph, and adapter-only AutoGen transfer, the frozen pipeline localizes **injected** communication faults under a shared single-edit budget.
- On official SWE-bench Verified (\(n=100\), LF-fixed harness), CR recovers the injected gold edge on every instance (gold-edge hit \(1.00\) vs reward-only \(0.33\); proxy \(0.97\)), but **Resolve@1 does not improve** (CR \(0.02\) vs baselines \(0.03\)–\(0.04\); non-significant).
- In this pipeline, most CR-guided end-to-end failures are patch apply / synthesis errors; an oracle gold-patch control reaches Resolve@1 \(0.89\) on the same list (harness validity).

Authoritative claim status: [`docs/CLAIMS_LEDGER.md`](docs/CLAIMS_LEDGER.md). Full protocol and commands: [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md).

## Repository structure

```text
commscm/              Core method, adapters (LangGraph / AutoGen / SWE-bench / WebArena), experiments, tests
credit_assignment/    Earlier credit-assignment utilities used by demo scripts
data/                 Task / fixture data
results/              Aggregated metrics, predictions, harness reports, and root-level run artifacts
logs/                 SWE-bench evaluation logs
docs/                 Process history (decision log, research log, claims ledger)
REPRODUCIBILITY.md    Seeds, pins, harness commits, how to reproduce cited runs
main.py               Small demo entrypoint (credit-assignment workshop demo)
run_experiments.py    Batch experiment loop for the credit-assignment demo
requirements.txt      Python dependencies
LICENSE               MIT
```

## How to reproduce

See **[`REPRODUCIBILITY.md`](REPRODUCIBILITY.md)** for the locked VI.B protocol, environment pins, and artifact paths.

Quickstart (demo only — not the full SWE-bench campaign):

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
# put OPENAI_API_KEY in a local .env (never commit it)
python main.py
# or:
python run_experiments.py --n-runs 12 --mock
```

Official SWE-bench Verified runs require Docker, the pinned SWE-bench harness, and substantial disk/time; follow `REPRODUCIBILITY.md` and the Part VI.B preregistration under `commscm/`.

## License

MIT — see [`LICENSE`](LICENSE).
## Project history

Internal freeze / falsification process notes live under [`docs/`](docs/) (e.g. [`docs/DECISION_LOG.md`](docs/DECISION_LOG.md), [`docs/RESEARCH_LOG.md`](docs/RESEARCH_LOG.md)). They document how the method was locked for evaluation; they are not required to use the code.
