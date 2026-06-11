"""
Labeling-specific data models.

The message map is the labeling analogue of Track 3's ContentSpec: a structured,
pre-prose alignment artifact for CCDS authoring. It is generated from the
competitive intelligence twin (the approved-label landscape) plus the molecule
content twin, then reviewed claim-by-claim and locked.
"""
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
import datetime


class Achievability(str, Enum):
    HIGH = "high"      # Strong precedent; our data meets or exceeds the bar
    MEDIUM = "medium"  # Precedent exists; data borderline or FDA has questioned similar claims
    LOW = "low"        # Claim is novel or data does not meet precedent threshold


class ApprovedClaim(BaseModel):
    """A single claim extracted from a competitor's approved product label.
    The atomic unit of the competitive intelligence twin."""
    claim_id: str
    drug_name: str
    indication: str
    label_section: str
    claim_text: str
    evidence_standard: str
    quantitative_threshold: Optional[str] = None
    approval_date: str = ""
    source_label: str = ""
    source_url: str = ""
    regulatory_notes: str = ""


class CompetitiveIntelligenceTwin(BaseModel):
    """Structured representation of the approved-label landscape for a given
    indication class and regulatory body. One twin per indication class."""
    ci_twin_id: str
    indication_class: str
    drug_class: str
    regulatory_body: str
    version: str
    last_updated: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    approved_claims: list[ApprovedClaim] = Field(default_factory=list)
    claims_by_section: dict = Field(default_factory=dict)  # section -> [claim_ids]


class MessageMapClaim(BaseModel):
    """A single proposed label claim in the message map (labeling analogue of SpecClaim)."""
    claim_id: str
    label_section: str
    proposed_claim_text: str
    supporting_element_id: str
    supporting_value: Any = None
    regulatory_precedent_ids: list[str] = Field(default_factory=list)
    precedent_summary: str = ""
    achievability: Achievability
    risk_note: str = ""
    confidence: float = 0.0
    confidence_rationale: str = ""
    is_gap: bool = False
    back_propagate: bool = False


class MessageMap(BaseModel):
    """The complete message map for a labeling document — the labeling-specific
    content specification."""
    map_id: str
    program_name: str
    indication: str
    document_type: str
    regulatory_body: str
    ci_twin_id: str
    content_twin_id: str
    generated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    generated_by_role: str = ""
    claims: list[MessageMapClaim] = Field(default_factory=list)

    high_achievability_count: int = 0
    medium_achievability_count: int = 0
    low_achievability_count: int = 0
    gaps_detected: list[str] = Field(default_factory=list)
    gaps_filled: list[str] = Field(default_factory=list)

    qc_passed: bool = False
    locked: bool = False
    locked_at: Optional[datetime.datetime] = None
    locked_by: Optional[str] = None
    version: str = "draft"

    def recount(self) -> None:
        """Recompute achievability tallies and gap list from current claims."""
        self.high_achievability_count = sum(
            1 for c in self.claims if c.achievability == Achievability.HIGH)
        self.medium_achievability_count = sum(
            1 for c in self.claims if c.achievability == Achievability.MEDIUM)
        self.low_achievability_count = sum(
            1 for c in self.claims if c.achievability == Achievability.LOW)
        self.gaps_detected = [c.claim_id for c in self.claims if c.is_gap]


class LabelingSession(BaseModel):
    """Full lifecycle of a labeling message map session."""
    session_id: str
    simulation_mode: str
    program_name: str
    indication: str
    ci_twin_id: str
    content_twin_id: str
    reference_label: str = "orforglipron (Foundayo)"   # selected comparator (v2 UX)
    map_id: Optional[str] = None

    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    phase: str = "setup"   # setup | ci_review | map_review | qc | locked | complete

    step_timings: list[dict] = Field(default_factory=list)

    claims_total: int = 0
    claims_high: int = 0
    claims_medium: int = 0
    claims_low: int = 0
    gaps_detected: int = 0
    gaps_filled_jit: int = 0
    reviewer_decisions: int = 0
    back_propagations: int = 0

    survey_response: Optional[dict] = None
    status: str = "in_progress"

    # CI Review reviewer overrides (program-specific; do not mutate the shared CI twin)
    ci_signal_overrides: dict = Field(default_factory=dict)   # section -> "HIGH"|"MED"|"GAP"
    ci_action_overrides: dict = Field(default_factory=dict)   # section -> "adopt"|"adapt"|"new"|"skip"
    strategic_insight_override: Optional[str] = None

    # Draft generation and review outcomes (label-draft extension)
    draft_id: Optional[str] = None
    draft_content_revision_requests: int = 0   # content_change type only
    draft_total_revision_requests: int = 0     # all types
    draft_overall_quality_rating: Optional[float] = None
    draft_regulatory_language_rating: Optional[float] = None
    draft_precedent_alignment_rating: Optional[float] = None
    draft_ready_for_revision_rating: Optional[float] = None


class LabelingSurveyResponse(BaseModel):
    participant_id: str
    role: str
    submitted_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    # Core ratings (1-10)
    process_preference: int       # message-map-first preferable to manual CI + authoring?
    ci_summary_quality: int       # usefulness of the CI summary
    achievability_accuracy: int   # accuracy of the achievability ratings
    risk_note_quality: int        # usefulness of the risk notes
    overall_confidence: int       # confidence in the locked message map
    time_saved_rating: int        # 1=took more time, 5=same, 10=saved significant time

    most_valuable_feature: str = ""
    biggest_gap: str = ""
    would_use_in_production: str = ""  # yes | yes, with changes | no
    changes_needed: str = ""
