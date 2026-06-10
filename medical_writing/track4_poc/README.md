# Track 4 POC — RA Workflow Integration

Structure Therapeutics | Workflow-integration sibling of Track 3 (RA analogue of Track 2).

Track 4 proves that the structured content specification pipeline — generated
from the regulatory framework twin + content twin, QC-checked, and reviewed via
a role-specific interface — produces **measurable workflow value**:

- **Hypothesis 1 — EOP2 Alignment:** spec-first alignment reaches locked content
  agreement faster, with fewer post-authoring content revision requests, than
  document-level debate.
- **Hypothesis 2 — Role-Based Review:** role-specific review packages produce
  higher reviewer confidence and fewer missed findings than unfiltered prose.

LLM components are simulated (Track 3 stub architecture). Real timing and
survey data are collected from human participants.

## Shared infrastructure

`core/`, `twins/`, `regulatory/`, `generation/`, `qc/`, `review/`,
`governance/`, `llm/`, `ingestion/` and the twin/checklist data dirs are
**symlinks into `../track3_poc`** — Track 4 adds only the human workflow layer:

```
workflow/
├── session.py       # AlignmentSession lifecycle + persistence
├── participant.py   # Participant timing/decision helpers
├── handoff.py       # SpecHandoff — locked spec → Track 2 prose generation
├── timer.py         # StepTimer — per-step timing capture
├── survey.py        # Post-session experiential survey
└── evaluator.py     # WorkflowEvaluator — all Track 4 metrics
```

## Quickstart

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt

venv/bin/python -m pytest -q                 # tests
venv/bin/python -m cli.main session start    # CLI
venv/bin/streamlit run app/streamlit_app.py --server.port 8504
```

## Session flow

Operator Setup → Spec Review (RA) → Alignment Session (all roles) → Spec Lock
→ Handoff to MW → Post-Prose Review → Survey → Results Dashboard

The locked-spec **handoff package** (JSON, `data/handoffs/`) is the formal
input to Track 2's prose generation workflow.
