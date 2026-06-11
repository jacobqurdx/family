"""
LabelingEvaluator: computes Track 5 outcome metrics from session data.
"""
import datetime

import pandas as pd

from labeling.labeling_models import LabelingSession


class LabelingEvaluator:
    def evaluate_session(self, session: LabelingSession) -> dict:
        survey = session.survey_response or {}
        timings = {t["step"]: t["timestamp"] for t in session.step_timings}

        # Elapsed time from map generation start (or session creation) to lock
        elapsed_minutes = None
        if "map_locked" in timings:
            start_iso = timings.get("map_generation_start") or session.created_at.isoformat()
            start = datetime.datetime.fromisoformat(start_iso)
            end = datetime.datetime.fromisoformat(timings["map_locked"])
            elapsed_minutes = round((end - start).total_seconds() / 60, 1)

        return {
            "session_id": session.session_id,
            "simulation_mode": session.simulation_mode,
            "program": session.program_name,
            "claims_total": session.claims_total,
            "claims_high": session.claims_high,
            "claims_medium": session.claims_medium,
            "claims_low": session.claims_low,
            "gaps_detected": session.gaps_detected,
            "gaps_filled_jit": session.gaps_filled_jit,
            "back_propagations": session.back_propagations,
            "reviewer_decisions": session.reviewer_decisions,
            "elapsed_minutes": elapsed_minutes,
            # Survey
            "process_preference": survey.get("process_preference"),
            "ci_summary_quality": survey.get("ci_summary_quality"),
            "achievability_accuracy": survey.get("achievability_accuracy"),
            "risk_note_quality": survey.get("risk_note_quality"),
            "overall_confidence": survey.get("overall_confidence"),
            "time_saved_rating": survey.get("time_saved_rating"),
            "would_use_in_production": survey.get("would_use_in_production"),
            # Label-draft extension metrics
            "draft_overall_quality": session.draft_overall_quality_rating,
            "draft_reg_language_quality": session.draft_regulatory_language_rating,
            "draft_precedent_alignment": session.draft_precedent_alignment_rating,
            "draft_ready_for_revision": session.draft_ready_for_revision_rating,
            "draft_content_revisions": session.draft_content_revision_requests,
            "draft_total_revisions": session.draft_total_revision_requests,
        }

    def to_dataframe(self, sessions: list) -> pd.DataFrame:
        return pd.DataFrame([self.evaluate_session(s) for s in sessions])
