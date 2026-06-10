"""
QC finding and review data models.

QCFinding is the atomic output of every QC pass. ReviewDecision captures a
structured reviewer response (from → to), replacing informal tracked-changes.
ReviewPackage is the role-specific bundle presented to a single reviewer.
"""
from typing import Optional
from pydantic import BaseModel, Field
import datetime


class QCFinding(BaseModel):
    finding_id: str
    section_id: str
    pass_number: int                 # 1=consistency 2=historical 3=checklist 4=metacognitive 5=role
    severity: str                    # "blocking" | "major" | "minor"
    category: str                    # "internal_inconsistency" | "prior_crl_concern" |
                                     # "checklist_violation" | "low_confidence" | "guidance_gap"
    description: str
    offending_text: Optional[str] = None
    role_relevance: list[str] = Field(default_factory=list)
    suggested_resolution: str = ""
    prior_position_id: Optional[str] = None


class ReviewDecision(BaseModel):
    """
    A structured reviewer decision on a single QC finding or spec section.
    Replaces the informal tracked-changes-in-Word approach.
    """
    decision_id: str
    finding_id: Optional[str] = None
    section_id: str
    reviewer_role: str
    decision: str                    # "accept"|"correct"|"suggest"|"flag_for_discussion"|"override"
    from_value: Optional[str] = None
    to_value: Optional[str] = None
    justification: str = ""          # required for override decisions
    back_propagate: bool = False     # should this correction be written to content twin?
    decided_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)


class ReviewPackage(BaseModel):
    """
    The complete role-specific review bundle presented to a single reviewer.
    """
    package_id: str
    spec_id: str
    reviewer_role: str
    primary_sections: list[str] = Field(default_factory=list)  # sections this role owns
    all_findings: list[QCFinding] = Field(default_factory=list)  # V1: all findings visible
    role_findings: list[QCFinding] = Field(default_factory=list)  # post-launch: filtered
    decisions: list[ReviewDecision] = Field(default_factory=list)
    completed: bool = False
    completed_at: Optional[datetime.datetime] = None
