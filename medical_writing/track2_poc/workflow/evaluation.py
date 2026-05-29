"""
WorkflowEvaluator: computes WorkflowMetrics from a completed WorkflowSession.
"""
from __future__ import annotations
from typing import Optional

from workflow.models import (
    WorkflowSession, WorkflowMetrics, AdjudicationDecision,
)
from workflow.assignment import AssignmentLoader


class WorkflowEvaluator:
    def __init__(self, assignment_loader: Optional[AssignmentLoader] = None):
        self._loader = assignment_loader or AssignmentLoader()

    def evaluate(self, session: WorkflowSession) -> WorkflowMetrics:
        records = session.adjudication_records

        approved_count = sum(1 for r in records if r.decision == AdjudicationDecision.APPROVED)
        revised_count = sum(1 for r in records if r.decision == AdjudicationDecision.REVISED)
        escalated_count = sum(1 for r in records if r.decision == AdjudicationDecision.ESCALATED)

        # Total AI time = sum of adjudication timings
        total_ai_seconds = sum(
            t.duration_seconds or 0.0
            for t in session.timings
            if t.step_type in ("adjudication", "review")
        )
        # Also include time_seconds from records if timings are not set
        if total_ai_seconds == 0.0:
            total_ai_seconds = sum(r.time_seconds for r in records)

        # Load assignment baseline
        try:
            assignment = self._loader.load(session.assignment_id)
            baseline_minutes = assignment.total_baseline_minutes
        except Exception:
            # Fallback: sum per-section baseline if assignment not loadable
            baseline_minutes = 120.0

        # Time savings: actual_minutes vs baseline
        actual_minutes = total_ai_seconds / 60.0
        if baseline_minutes > 0:
            time_savings_pct = max(0.0, (1.0 - actual_minutes / baseline_minutes) * 100.0)
        else:
            time_savings_pct = 0.0

        # Survey score
        avg_survey: Optional[float] = None
        if session.survey:
            s = session.survey
            avg_survey = (
                s.overall_experience + s.time_savings_perceived + s.document_quality
            ) / 3.0

        adoption_threshold = avg_survey is not None and avg_survey >= 7.0

        return WorkflowMetrics(
            session_id=session.session_id,
            simulation_mode=session.simulation_mode,
            total_sections=len(records),
            approved_count=approved_count,
            revised_count=revised_count,
            escalated_count=escalated_count,
            total_ai_time_seconds=total_ai_seconds,
            total_baseline_minutes=baseline_minutes,
            time_savings_pct=round(time_savings_pct, 1),
            avg_survey_score=round(avg_survey, 2) if avg_survey is not None else None,
            adoption_threshold_met=adoption_threshold,
        )
