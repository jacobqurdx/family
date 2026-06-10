# Track 3 POC — AI Regulatory Intelligence System

Structure Therapeutics | Regulatory Affairs sibling of Track 1.

Track 3 shares Track 1's core infrastructure (twin hierarchy, schema engine,
dependency graph) and adds the regulatory-specific components:

- **Regulatory framework twin** — FDA/EMA guidance requirements + agency concerns + prior positions
- **Guidance ingestion pipeline** — PDF/docx → structured requirements (stubbed)
- **Content specification generator** — `f(Content Twin, Document Structure Twin) → ContentSpec`
- **Five-pass QC pipeline** — consistency · historical · checklist · metacognitive · role routing
- **Role-based review + governance** — permissions, locking, versioning (simulated)

## Two twin types per document

| Twin | "Question it answers" | Tier | Example |
|---|---|---|---|
| **Content Twin** | What we know | molecule / trial | `molecule_aleniglipron.json` |
| **Document Structure Twin** | How the doc must be shaped | company / framework | `structure_eop2_fda.json` |

Document generation is always `f(Content Twin, Document Structure Twin) → Document`.

## Quickstart

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# Tests
venv/bin/python -m pytest -q

# CLI
venv/bin/python -m cli.main structure show structure_eop2_fda
venv/bin/python -m cli.main spec generate
venv/bin/python -m cli.main qc run

# Streamlit
venv/bin/streamlit run app/streamlit_app.py --server.port 8503
```

## Simulation modes

All LLM components are **stubbed** (`USE_STUB=true`). Each stub honours `SIMULATION_MODE`:

- `high_quality` — plausible output, confidence ≥ 0.80
- `low_quality` — deliberate issues + confidence ≤ 0.50, to exercise the QC pipeline

```bash
SIMULATION_MODE=low_quality venv/bin/python -m cli.main qc run
```

Every stub carries a `# PROMOTION SLOT:` marker where the functional LLM model drops in.
