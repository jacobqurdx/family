# Track 5 POC — Labeling Workflow Integration

Structure Therapeutics | Labeling extension of the RA AI system (BRD v02 Appendix B).

Track 5 proves one focused hypothesis:

> A regulatory affairs reviewer who receives a pre-generated, CI-grounded **message
> map** — claim by claim, with competitive precedent citations and achievability
> ratings — reaches a locked message map faster and with greater confidence than
> the current manual approach of synthesizing competitive intelligence from scratch.

This is a **workflow POC only**. Technical feasibility (content-spec generation,
QC, role-based review) is proven by Track 3 and reused directly.

## What this is not
- Not a CCDS prose-generation POC (that's Track 1/2).
- Not a competitive-label ingestion pipeline (the CI twin is hand-populated from
  public approved labels — Wegovy, Zepbound, Saxenda — sourced from DailyMed).
- Not a country-label derivation POC.
- The message map generator (**LLM-14**) is stubbed with high/low quality modes.

## Shared infrastructure

`core/`, `twins/`, `regulatory/`, `qc/`, `review/`, `governance/`, `llm/` and the
content-twin data are **symlinks into `../track3_poc`**. Track 5 adds:

```
labeling/
├── labeling_models.py        # ApprovedClaim, CITwin, MessageMap(Claim), LabelingSession, survey
├── ci_twin.py                # CITwinManager — query the approved-label landscape
├── message_map.py            # MessageMapManager — persist/lock message maps
├── message_map_generator.py  # MessageMapGenerator (LLM-14 stub, high/low quality)
├── labeling_qc.py            # LabelingQCValidator — labeling checklist (claim-type + precedent)
├── draft_models.py           # LabelDraft, LabelSection, DraftReviewResult, DraftRevisionRequest
└── label_draft_generator.py  # LabelDraftGenerator (LLM-15 stub) — CCDS prose from locked map
workflow/
├── session.py                # LabelingSession re-export + SessionManager persistence
├── timer.py · survey.py · evaluator.py
```

## Quickstart

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt

venv/bin/python -m pytest -q
venv/bin/python -m cli.main ci show ci_glp1_obesity_fda
venv/bin/python -m cli.main map generate
venv/bin/streamlit run app/streamlit_app.py --server.port 8505
```

## Session flow

Operator Setup → CI Review → Message Map Review (claim by claim) → QC Pipeline
(labeling checklist) → Message Map Lock → **Label Draft** (CCDS prose from the
locked map) → **Draft Review** (rate quality, log content revisions) → Survey →
Results Dashboard.

The label-draft extension closes the loop from CI synthesis to a reviewable
CCDS draft. The end-to-end hypothesis: a draft generated from a CI-grounded
message map needs **fewer content revision requests** than one from a
low-quality map.

## LLM workstream items (stubbed here)
- **LLM-13 Competitive Label Extractor** — auto-populates the CI twin from DailyMed/FDA labels.
- **LLM-14 Message Map Generator** — generates the full message map (promotion slot in `message_map_generator.py`).
- **LLM-15 Label Draft Generator** — generates CCDS section prose from a locked message map (promotion slot in `label_draft_generator.py`); shares LLM-01 infrastructure with labeling-specific prompts.
