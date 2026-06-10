"""
AlignmentSession: the full lifecycle of a Track 4 EOP2 alignment session.

Phases: SETUP → RA_REVIEW → ALIGNMENT → LOCKED → HANDOFF → POST_PROSE_REVIEW
→ COMPLETE. The session record accumulates timing, gap/QC outcome counts,
content revision requests and survey responses — the raw data for both Track 4
hypotheses. SessionManager persists sessions to SESSIONS_DIR for the
cross-session results dashboard.
"""
from enum import Enum
from typing import Optional
from pathlib import Path
from pydantic import BaseModel, Field
import datetime
import json

import config


class SessionPhase(str, Enum):
    SETUP = "setup"
    RA_REVIEW = "ra_review"           # RA lead reviews QC findings, resolves gaps
    ALIGNMENT = "alignment"           # All participants review spec together
    LOCKED = "locked"                 # Spec locked by RA lead
    HANDOFF = "handoff"               # Locked spec handed off to medical writing
    POST_PROSE_REVIEW = "post_prose"  # Review of prose generated from locked spec
    COMPLETE = "complete"


class ParticipantRecord(BaseModel):
    participant_id: str
    role: str          # regulatory_affairs | medical_writing | clinical_science | clinical_operations
    joined_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    review_started_at: Optional[datetime.datetime] = None
    review_completed_at: Optional[datetime.datetime] = None
    decisions_made: int = 0
    survey_completed: bool = False


class StepTiming(BaseModel):
    step_name: str
    started_at: datetime.datetime
    completed_at: Optional[datetime.datetime] = None

    @property
    def duration_minutes(self) -> Optional[float]:
        if self.completed_at:
            delta = self.completed_at - self.started_at
            return round(delta.total_seconds() / 60, 1)
        return None


class SurveyResponse(BaseModel):
    participant_id: str
    role: str
    submitted_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    # Core experiential ratings (1-10)
    alignment_process_preference: int   # spec-first preferable to document-level debate?
    spec_quality_rating: int            # usefulness of the pre-generated content spec
    qc_findings_utility: int            # usefulness of the pre-generated QC findings
    role_review_clarity: int            # clarity of the role-specific review interface
    confidence_in_document: int         # confidence in the final document based on the spec
    likelihood_of_content_revisions: int  # 1=very likely to revise, 10=very unlikely

    # Free text
    what_worked: str = ""
    what_didnt_work: str = ""
    biggest_time_saver: str = ""
    biggest_friction: str = ""


class ContentRevisionRequest(BaseModel):
    """
    A content change request raised after prose is generated from the locked spec.
    Key outcome metric: fewer content revision requests = the locked spec did its
    job. Only change_type == "content_change" counts against the hypothesis;
    formatting and language changes are expected and acceptable.
    """
    request_id: str
    requesting_role: str
    section_id: str
    description: str
    change_type: str                   # "content_change" | "formatting" | "language"
    raised_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)


class AlignmentSession(BaseModel):
    session_id: str
    simulation_mode: str               # "high_quality" | "low_quality"
    document_type: str                 # e.g. "eop2_briefing"
    content_twin_id: str
    structure_twin_id: str
    spec_id: Optional[str] = None      # set after spec is generated
    handoff_id: Optional[str] = None   # set after spec is locked and handed off

    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    phase: SessionPhase = SessionPhase.SETUP
    participants: list[ParticipantRecord] = Field(default_factory=list)
    step_timings: list[StepTiming] = Field(default_factory=list)

    # Outcome data
    gaps_detected: int = 0
    gaps_filled_jit: int = 0
    qc_findings_total: int = 0
    qc_findings_blocking: int = 0
    review_decisions_total: int = 0
    content_revision_requests: list[ContentRevisionRequest] = Field(default_factory=list)

    # Surveys
    survey_responses: list[SurveyResponse] = Field(default_factory=list)

    status: str = "in_progress"

    # ── Convenience API ───────────────────────────────────────────────────────

    def get_participant(self, role: str) -> Optional[ParticipantRecord]:
        return next((p for p in self.participants if p.role == role), None)

    def start_step(self, step_name: str) -> StepTiming:
        timing = StepTiming(step_name=step_name,
                            started_at=datetime.datetime.utcnow())
        self.step_timings.append(timing)
        return timing

    def complete_step(self, step_name: str) -> Optional[StepTiming]:
        """Close the most recent open timing with this step name."""
        for timing in reversed(self.step_timings):
            if timing.step_name == step_name and timing.completed_at is None:
                timing.completed_at = datetime.datetime.utcnow()
                return timing
        return None


class SessionManager:
    """Persist and reload alignment sessions (JSON under SESSIONS_DIR)."""

    def __init__(self, sessions_dir: Optional[str] = None):
        self._dir = Path(sessions_dir or config.SESSIONS_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, session: AlignmentSession) -> None:
        path = self._dir / f"{session.session_id}.json"
        path.write_text(session.model_dump_json(indent=2))

    def load(self, session_id: str) -> AlignmentSession:
        path = self._dir / f"{session_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")
        return AlignmentSession(**json.loads(path.read_text()))

    def list_sessions(self) -> list:
        sessions = []
        for f in sorted(self._dir.glob("*.json")):
            try:
                sessions.append(self.load(f.stem))
            except Exception:
                pass
        return sessions
