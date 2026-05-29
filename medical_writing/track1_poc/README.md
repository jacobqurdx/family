# Track 1 POC — AI Clinical Document Intelligence System

**Structure Therapeutics | Technical Feasibility POC**

Track 1 proves three technical hypotheses:

1. A generic, schema-driven dependency graph engine can model any clinical document type and correctly propagate changes through dependent elements.
2. An LLM can generate regulatory-quality prose from structured schema data with measurable, calibrated accuracy.
3. The system can detect cross-document inconsistencies by comparing element values across two document instances that share schema elements.

## Setup

```bash
cd track1_poc
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY if testing real LLM
# USE_STUB=true by default (no API calls needed)
```

## CLI Usage

```bash
# Schema commands
python -m cli.main schema list
python -m cli.main schema show protocol
python -m cli.main schema validate protocol

# Twin commands
python -m cli.main twin show synth_phase2_trial
python -m cli.main twin set synth_phase2_trial primary_endpoint "change from baseline in FPG"
python -m cli.main twin diff synth_phase2_trial <other_twin_id>

# Dependency commands
python -m cli.main dep graph protocol
python -m cli.main dep propagate synth_phase2_trial primary_endpoint
python -m cli.main dep check synth_phase2_trial <other_twin_id>

# Generation commands
python -m cli.main generate section synth_phase2_trial primary_endpoint_narrative
python -m cli.main generate document synth_phase2_trial

# Evaluation commands
python -m cli.main evaluate accuracy
python -m cli.main evaluate calibration
python -m cli.main evaluate consistency synth_phase2_trial <other_twin_id>
```

## Streamlit App

```bash
streamlit run app/streamlit_app.py
```

Pages:
- **Schema Explorer** — schema elements and dependency graph visualization
- **Twin Editor** — guided authoring with live propagation
- **Dependency Graph** — interactive propagation simulator
- **Prose Generator** — AI section generation + QC
- **QC Agent** — batch QC across all sections
- **LLM Testbed** — accuracy and calibration evaluation

## Tests

```bash
pytest tests/ -v
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | `""` | Required only when `USE_STUB=false` |
| `USE_STUB` | `true` | `false` to use real Claude API |

## Project Structure

```
track1_poc/
├── core/           # Schema engine, Digital Twin, Dependency Graph, models
├── llm/            # Stub, LLM client, prompts, testbed
├── generation/     # ProseGenerator, QCAgent
├── data/           # Schemas (JSON), twins, ground truth pairs
├── cli/            # Click CLI
├── app/            # Streamlit pages
└── tests/          # pytest test suite
```
