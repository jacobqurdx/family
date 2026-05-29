# Track 2 POC — AI Clinical Document Intelligence System

AI-assisted downstream writer workflow for regulatory document authoring.

## Quick Start

```bash
cd track2_poc
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python scripts/generate_synth_protocol.py
python3 -m pytest tests/ -v --tb=short
streamlit run app/streamlit_app.py
```

## Architecture

- `core/` — Digital twin models (shared with Track 1)
- `usdm/` — 57-node USDM graph (9 layers) + LLM extractor
- `ingestion/` — Layer-by-layer document ingestion pipeline
- `workflow/` — Writer adjudication workflow and evaluation
- `cli/` — Click CLI
- `app/` — Streamlit multi-page app (9 pages)
- `data/` — Schemas, twins, assignments, simulated outputs
- `tests/` — Pytest test suite

## Environment

```
ANTHROPIC_API_KEY=your_key_here   # optional; stub mode used if absent
SIMULATION_MODE=high_quality      # high_quality or low_quality
```
