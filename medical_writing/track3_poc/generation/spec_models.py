"""
Content specification data models.

A content specification is a structured, pre-prose outline: required sections,
the claims that must appear in each, and the content-twin data references that
support each claim. It is the output of the content spec generator and the
input to the (downstream) document prose generator. It is NOT prose.
"""
from typing import Any, Optional
from pydantic import BaseModel, Field
import datetime


class SpecClaim(BaseModel):
    """
    A single claim within a content specification section.
    Each claim is traceable to a content twin element and a structure requirement.
    """
    claim_id: str
    claim_text: str                      # the claim as it should appear in the document
    supporting_element_id: str           # content twin element ID supporting this claim
    supporting_value: Any = None         # the actual value from the content twin
    confidence: float = 0.0              # 0.0 - 1.0
    confidence_rationale: str = ""
    is_gap: bool = False                 # True if supporting value was missing from twin
    gap_filled_by: Optional[str] = None  # role that filled the gap JIT
    regulatory_authority: str = ""       # which guidance requires this claim


class SpecSection(BaseModel):
    """
    A single section of the content specification.
    Maps to one SectionRequirement in the document structure twin.
    """
    section_id: str
    section_title: str
    required: bool = True
    claims: list[SpecClaim] = Field(default_factory=list)
    qc_findings: list[str] = Field(default_factory=list)   # finding IDs, populated after QC
    role_primary: list[str] = Field(default_factory=list)
    overall_confidence: float = 0.0
    needs_human_review: bool = False     # True if metacognitive flagger fired


class ContentSpec(BaseModel):
    """
    The complete structured content specification for a document.
    """
    spec_id: str
    document_type: str
    content_twin_id: str
    structure_twin_id: str
    generated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    generated_by_role: str = ""
    sections: list[SpecSection] = Field(default_factory=list)
    gaps_detected: list[str] = Field(default_factory=list)  # element IDs missing from twin
    gaps_filled: list[str] = Field(default_factory=list)    # element IDs filled JIT
    qc_passed: bool = False
    locked: bool = False
    locked_at: Optional[datetime.datetime] = None
    locked_by: Optional[str] = None
    version: str = "draft"
