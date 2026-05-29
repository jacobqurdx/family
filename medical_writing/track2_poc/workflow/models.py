from __future__ import annotations
from enum import Enum
from typing import Any, Optional, List, Dict
from pydantic import BaseModel, Field
import datetime


class AdjudicationDecision(str, Enum):
    APPROVED = "approved"
    REVISED = "revised"
    ESCALATED = "escalated"


class StepTiming(BaseModel):
    step_id: str
    step_type: str        # "review" | "adjudication" | "survey"
    started_at: datetime.datetime
    completed_at: Optional[datetime.datetime] = None
    duration_seconds: Optional[float] = None


class AdjudicationRecord(BaseModel):
    section_id: str
    section_title: str
    decision: AdjudicationDecision
    simulated_prose: str
    final_prose: str
    revision_notes: Optional[str] = None
    time_seconds: float = 0.0
    adjudicated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)


class SurveyRating(BaseModel):
    overall_experience: int          # 1-10
    time_savings_perceived: int      # 1-10
    document_quality: int            # 1-10
    would_use_again: bool
    free_text: Optional[str] = None
    submitted_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)


class SimulatedOutput(BaseModel):
    section_id: str
    section_title: str
    prose: str
    quality_tier: str              # "high_quality" | "low_quality"
    simulated_confidence: float
    source_elements: Dict[str, Any] = Field(default_factory=dict)


class AssignedSection(BaseModel):
    section_id: str
    section_title: str
    source_elements: List[str]
    baseline_minutes: float
    prompt_template: str


class DocumentAssignment(BaseModel):
    assignment_id: str
    document_type: str              # "csr" | "protocol_amendment" | "icf"
    title: str
    description: str
    sections: List[AssignedSection]
    total_baseline_minutes: float


class WorkflowSession(BaseModel):
    session_id: str
    writer_id: str
    assignment_id: str
    twin_id: str
    simulation_mode: str            # "high_quality" | "low_quality"
    started_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    completed_at: Optional[datetime.datetime] = None
    timings: List[StepTiming] = Field(default_factory=list)
    adjudication_records: List[AdjudicationRecord] = Field(default_factory=list)
    survey: Optional[SurveyRating] = None
    status: str = "in_progress"     # "in_progress" | "complete"


class WorkflowMetrics(BaseModel):
    session_id: str
    simulation_mode: str
    total_sections: int
    approved_count: int
    revised_count: int
    escalated_count: int
    total_ai_time_seconds: float
    total_baseline_minutes: float
    time_savings_pct: float
    avg_survey_score: Optional[float] = None
    adoption_threshold_met: bool     # avg_survey >= 7.0
