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
├── label_draft_generator.py  # LabelDraftGenerator (LLM-15 stub) — CCDS prose from locked map
└── ci_analysis.py            # achievability table · strategic insight · comparator detail · diff rows
workflow/
├── session.py                # LabelingSession re-export + SessionManager persistence
├── ui.py                     # wizard stepper + Hub step-status logic (v2 navigation)
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

## Navigation (v2 — wizard-first, hub-after)

First run walks an 8-step wizard in order; a progress stepper sits at the top of
every wizard page. Return visits land on the **Hub** (page 0), which shows status
across all steps and lets you jump to any of them.

```
0 Hub  ·  1 Operator Setup  ·  2 CI Review  ·  3 Message Map  ·  4 QC  ·
5 Lock  ·  6 Draft Bridge  ·  7 Claim Inspector  ·  8 Survey  ·  9 Results Dashboard
```

Key v2 screens:
- **CI Review** — full-width strategic insight bar + achievability ceiling table
  (5 CCDS sections, HIGH/MED/GAP signals) + per-comparator detail with
  adopt/adapt/skip chips. Foundayo (orforglipron) is the default reference.
- **Message Map** — each CCDS section is one full-width row (reference · decision ·
  proposed) so the three columns stay aligned and the page scrolls as a unit;
  colour-coded reference highlights (🟣 adopt / 🟡 adapt / 🔴 diverge).
- **Draft Bridge** — locked claims (left) → generated prose (right), level rows,
  confidence bars, blue CI-traceable underlines, amber gap badges, approve/flag.
- **Claim Inspector** — Precision Chain: claim list · evidence chain
  (CI precedent → locked claim → generated) · wider draft column with assessment.

The end-to-end hypothesis: a draft generated from a CI-grounded message map needs
**fewer content revision requests** than one from a low-quality map.

## LLM workstream items (stubbed here)
- **LLM-13 Competitive Label Extractor** — auto-populates the CI twin from DailyMed/FDA labels.
- **LLM-14 Message Map Generator** — generates the full message map (promotion slot in `message_map_generator.py`).
- **LLM-15 Label Draft Generator** — generates CCDS section prose from a locked message map (promotion slot in `label_draft_generator.py`); shares LLM-01 infrastructure with labeling-specific prompts.
