# Pharma Supply Chain Risk Investigation Agent — POC

A supply chain risk investigation agent that monitors pharmaceutical supply chain signals,
assesses their relevance and severity against an MRP sensitivity profile, and triggers
quantitative re-analyses when actionable risks are detected.

## What it does

1. **Collects** signals from files or live web search (FDA alerts, Federal Register, trade press)
2. **Assesses** each signal through a 4-step LLM pipeline:
   - Relevance: is this signal about a monitored parameter?
   - Novelty: does it contain information beyond the current known state?
   - Severity: ROUTINE / ELEVATED / HIGH / CRITICAL
   - Impact: estimated $/kg API cost delta (for HIGH/CRITICAL only)
3. **Acts** on HIGH/CRITICAL signals: tariff sweep re-run, CDMO removal model, investigation reports, management briefings
4. **Evaluates** pipeline quality against a 30-signal labelled corpus with precision/recall/F1 metrics

## Quick start (no API key needed)

```bash
cd pharma-risk-agent-poc
pip install -e .

# Run evaluation against labelled corpus (stub mode — no API key)
agent evaluate --stub

# Run full loop against corpus signals
agent run examples/sensitivity_report_wuxi.json \
  --signal-dir corpus/signals \
  --process ../pharma-mrp-poc/examples/linear_5step.yaml \
  --prices ../pharma-mrp-poc/examples/prices_q2_2026.yaml \
  --risk-profile ../pharma-mrp-poc/examples/risk_profile_wuxi.yaml \
  --stub
```

## With real API key

```bash
export ANTHROPIC_API_KEY=sk-ant-...

# Generate a fresh sensitivity report
mrp risk-sensitivity \
  examples/linear_5step.yaml \
  examples/prices_q2_2026.yaml \
  examples/risk_profile_wuxi.yaml

# Run evaluation with real LLM
agent evaluate --sensitivity outputs/sensitivity_report.json

# Run live signal collection
agent run outputs/sensitivity_report.json
```

## Directory structure

```
pharma-risk-agent-poc/
├── agent/              Core pipeline modules
│   ├── domain.py       Dataclasses and enums
│   ├── llm.py          LLMClient (real + stub backends, disk cache)
│   ├── mrp.py          MRP POC integration (in-process import)
│   ├── state.py        Signal state persistence (JSON-backed)
│   ├── collector.py    Signal collection (file-based + live web)
│   ├── assessor.py     4-step assessment pipeline
│   ├── actions.py      Action execution (tariff sweep, CDMO removal, reports)
│   ├── eval.py         Evaluation harness (precision/recall/F1)
│   └── reporter.py     Output writers (JSON, Markdown)
├── prompts/            Versioned LLM prompt templates
├── corpus/
│   ├── signals/        30 labelled signal files (.json)
│   └── labels.yaml     Ground-truth labels for evaluation
├── examples/
│   └── sensitivity_report_wuxi.json   Pre-computed MRP sensitivity report
├── stub_responses/     Pre-written JSON responses for stub mode
├── tests/              Pytest test suite
├── cache/              LLM response disk cache (gitignored)
└── outputs/            Run outputs (gitignored)
```

## POC success criteria

`agent evaluate --stub` passes when:
- Relevance: precision ≥ 0.85, recall ≥ 0.85
- Novelty: F1 ≥ 0.80
- Severity (macro): F1 ≥ 0.80

## Requirements

- Python ≥ 3.11
- `pharma-mrp-poc` installed in the same environment (`pip install -e ../pharma-mrp-poc`)
- `anthropic>=0.28` (only needed for real mode)
