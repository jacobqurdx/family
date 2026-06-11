"""
Label draft data models (label-draft extension).

These models cover the final two stages of the labeling workflow: generating
CCDS section prose from a locked message map (LabelDraft / LabelSection) and the
reviewer's single-pass assessment of that draft (DraftReviewResult /
DraftRevisionRequest).
"""
from typing import Optional
from pydantic import BaseModel, Field
import datetime


class LabelSection(BaseModel):
    """A single generated section of the CCDS label draft. Maps one-to-one to a
    section in the document structure twin and is grounded in the locked message
    map claims for that section."""
    section_id: str
    section_title: str
    prose: str
    source_claim_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    confidence_rationale: str = ""
    has_gaps: bool = False
    model_used: str = "stub"
    prompt_version: str = "stub_v1"


class LabelDraft(BaseModel):
    """The complete generated CCDS draft, produced from a locked message map."""
    draft_id: str
    map_id: str
    program_name: str
    indication: str
    document_type: str
    regulatory_body: str
    generated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    simulation_mode: str
    sections: list[LabelSection] = Field(default_factory=list)
    overall_confidence: float = 0.0


class DraftRevisionRequest(BaseModel):
    """A revision request raised by the reviewer after reading the draft.
    Only change_type == 'content_change' counts against the POC hypothesis."""
    request_id: str
    section_id: str
    change_type: str                    # "content_change" | "formatting" | "language"
    description: str
    from_text: Optional[str] = None
    to_text: Optional[str] = None
    raised_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)


class DraftReviewResult(BaseModel):
    """The reviewer's complete single-pass assessment of the generated draft."""
    draft_id: str
    reviewer_role: str
    reviewed_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    section_ratings: dict = Field(default_factory=dict)   # section_id -> rating (1-10)

    overall_draft_quality: int
    regulatory_language_quality: int
    precedent_alignment: int
    ready_for_revision: int

    revision_requests: list[DraftRevisionRequest] = Field(default_factory=list)

    most_accurate_section: str = ""
    most_problematic_section: str = ""
    notes: str = ""

    @property
    def content_revision_count(self) -> int:
        return sum(1 for r in self.revision_requests if r.change_type == "content_change")
