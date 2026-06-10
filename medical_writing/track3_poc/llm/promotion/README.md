# Promotion Slots

Every LLM component in Track 3 ships as a **stub** under `llm/stubs/`. Each stub
implements the exact input signature and output Pydantic model of the functional
model the LLM workstream will eventually deliver, and carries a
`# PROMOTION SLOT: <ComponentName>` marker at the top of the file.

## How promotion works

When a functional model passes the eval harness at its minimum maturity
threshold, it "drops in" at the corresponding slot. Two changes are required:

1. Implement the functional class with the **same interface** as the stub.
2. Switch the import at the call site (or flip `USE_STUB=false` and add the
   functional import branch in `qc/pipeline.py::_load_components`).

No orchestration code changes.

## Slots and maturity gates

| Slot | Stub file | Interface | Promotion gate |
|---|---|---|---|
| `GuidanceExtractor` | `guidance_extractor_stub.py` | `extract_requirements(text, doc_type) -> list[RegulatoryRequirement]` | Alpha (eval ≥ threshold) |
| `ContentSpecGenerator` | `content_spec_stub.py` | `generate(twin_pair, content_twin, structure_twin) -> ContentSpec` | Alpha |
| `ConsistencyChecker` | `consistency_checker_stub.py` | `check(spec) -> list[QCFinding]` | Alpha |
| `HistoricalChecker` | `historical_checker_stub.py` | `check(spec, framework_twin) -> list[QCFinding]` | Beta (labeled CRL dataset) |
| `ChecklistValidator` | `checklist_validator_stub.py` | `validate(spec, checklist_path) -> list[QCFinding]` | Already real (rules explicit) |
| `MetacognitiveFlagger` | `metacognitive_stub.py` | `flag(spec) -> list[QCFinding]` | Beta (confidence calibration) |
| `RoleRouter` | `role_router_stub.py` | `route(findings, role) -> list[QCFinding]` | Post-launch (role filtering) |

## Quality modes

Stubs honour `config.SIMULATION_MODE`:

- `high_quality` — plausible output, confidence ≥ 0.80
- `low_quality` — deliberate issues, confidence ≤ 0.50

This lets the QC pipeline and review interface be exercised end-to-end with no
API calls and no functional models present.
