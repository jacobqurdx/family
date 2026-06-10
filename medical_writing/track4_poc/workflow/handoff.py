"""
SpecHandoff: packages a locked ContentSpec for handoff to the Medical Writing
Track 2 prose generation workflow.

The locked spec is the formal input to the prose generation step. It replaces
the informal brief (slide deck, annotated outline, verbal guidance) that
currently gets handed from regulatory affairs to medical writing.

The handoff format is a structured JSON package that Track 2 can ingest
directly — no interpretation required by the medical writer.
"""
import json
import datetime
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

from generation.spec_models import ContentSpec
import config


class HandoffPackage(BaseModel):
    """
    The formal handoff artifact from regulatory affairs to medical writing.
    This is what Track 2 ingests to generate prose.
    """
    handoff_id: str
    session_id: str
    spec_id: str
    document_type: str
    content_twin_id: str
    structure_twin_id: str
    locked_at: datetime.datetime
    locked_by: str                     # role that applied the version lock
    locked_spec_version: str

    # The full locked content specification
    sections: list[dict] = Field(default_factory=list)   # serialized SpecSection objects

    # Metadata for Track 2
    gaps_filled: list[str] = Field(default_factory=list)        # filled JIT during alignment
    back_propagated: list[str] = Field(default_factory=list)    # written back to content twin
    qc_findings_summary: dict = Field(default_factory=dict)     # {blocking: N, major: N, minor: N}
    review_decisions_summary: dict = Field(default_factory=dict)  # {accept: N, correct: N, ...}

    # Handoff notes from regulatory affairs to medical writing
    ra_notes: str = ""
    priority_sections: list[str] = Field(default_factory=list)  # sections needing most MW attention
    open_items: list[str] = Field(default_factory=list)         # items still to be resolved


class HandoffManager:
    def __init__(self, handoffs_dir: Optional[str] = None):
        self._dir = Path(handoffs_dir or config.HANDOFFS_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)

    def create(
        self, session_id: str, spec: ContentSpec,
        ra_notes: str = "", priority_sections: Optional[list] = None,
        qc_findings: Optional[list] = None,
        review_decisions_summary: Optional[dict] = None,
        back_propagated: Optional[list] = None,
        open_items: Optional[list] = None,
    ) -> HandoffPackage:
        if not spec.locked:
            raise ValueError("Spec must be version-locked before handoff.")

        findings_summary = {"blocking": 0, "major": 0, "minor": 0}
        for f in (qc_findings or []):
            sev = getattr(f, "severity", None) or f.get("severity")
            if sev in findings_summary:
                findings_summary[sev] += 1

        handoff = HandoffPackage(
            handoff_id=f"handoff_{session_id}_{spec.version}",
            session_id=session_id,
            spec_id=spec.spec_id,
            document_type=spec.document_type,
            content_twin_id=spec.content_twin_id,
            structure_twin_id=spec.structure_twin_id,
            locked_at=spec.locked_at or datetime.datetime.utcnow(),
            locked_by=spec.locked_by or "regulatory_affairs",
            locked_spec_version=spec.version,
            sections=[s.model_dump() for s in spec.sections],
            gaps_filled=spec.gaps_filled,
            back_propagated=back_propagated or [],
            qc_findings_summary=findings_summary,
            review_decisions_summary=review_decisions_summary or {},
            ra_notes=ra_notes,
            priority_sections=priority_sections or [],
            open_items=open_items or [],
        )
        path = self._dir / f"{handoff.handoff_id}.json"
        path.write_text(handoff.model_dump_json(indent=2))
        return handoff

    def load(self, handoff_id: str) -> HandoffPackage:
        path = self._dir / f"{handoff_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Handoff not found: {handoff_id}")
        return HandoffPackage(**json.loads(path.read_text()))

    def list_ids(self) -> list:
        return sorted(f.stem for f in self._dir.glob("*.json"))
