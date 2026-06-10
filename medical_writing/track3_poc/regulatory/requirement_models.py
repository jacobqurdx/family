"""
Regulatory framework twin data models.

The regulatory framework twin is the per-agency store of ingested guidance
requirements, known agency concerns, and prior company positions. It is the
authoritative source the QC pipeline checks generated content against.
"""
from typing import Optional
from pydantic import BaseModel, Field
import datetime


class RegulatoryRequirement(BaseModel):
    """
    A single extracted requirement from an FDA/EMA guidance document.
    The atomic unit of the regulatory framework twin.
    """
    requirement_id: str
    guidance_document_id: str
    guidance_section: str                       # section number and title in the guidance
    source_quote: str                           # verbatim text from guidance
    requirement_text: str                       # normalised requirement statement
    applies_to_document_types: list[str] = Field(default_factory=list)
    applies_to_indications: list[str] = Field(default_factory=list)  # empty = all
    requirement_type: str                       # "structure"|"content"|"format"|"process"
    mandatory: bool = True
    confidence: float = 1.0                     # extraction confidence
    verified_by: Optional[str] = None
    verified_at: Optional[datetime.datetime] = None


class AgencyConcern(BaseModel):
    """
    A known agency concern captured from CRL letters, meeting minutes, or
    guidance Q&As. Used by the historical issue checker (QC Pass 2).
    """
    concern_id: str
    source_type: str                            # "crl"|"meeting_minutes"|"guidance_qa"|"adcom"
    source_document: str
    indication_class: str                       # e.g. "obesity", "glp1_agonist"
    document_section: str                       # submission section the concern relates to
    concern_text: str
    resolution_guidance: str                    # what the agency expects to see
    program_id: Optional[str] = None            # if program-specific


class PriorPosition(BaseModel):
    """
    A regulatory position taken by Structure Therapeutics in a prior submission.
    Used by the historical issue checker to flag position inconsistency.
    """
    position_id: str
    program_id: str                             # e.g. "aleniglipron"
    document_type: str
    submission_date: str
    section: str
    position_text: str
    outcome: Optional[str] = None               # "accepted"|"questioned"|"rejected"
    notes: Optional[str] = None


class RegulatoryFrameworkTwin(BaseModel):
    """
    The complete regulatory framework twin for a specific regulatory body.
    One per regulatory body (FDA, EMA, PMDA).
    """
    framework_id: str                           # e.g. "framework_fda"
    regulatory_body: str                        # "FDA" | "EMA" | "PMDA"
    version: str
    last_updated: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    guidance_documents: list[dict] = Field(default_factory=list)
    requirements: list[RegulatoryRequirement] = Field(default_factory=list)
    agency_concerns: list[AgencyConcern] = Field(default_factory=list)
    prior_positions: list[PriorPosition] = Field(default_factory=list)
    locked: bool = False
