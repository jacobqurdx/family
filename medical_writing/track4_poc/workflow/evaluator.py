"""
WorkflowEvaluator: computes all Track 4 outcome metrics from session data.
Metrics are designed to answer the two Track 4 hypotheses directly.
"""
from typing import Optional

import pandas as pd

from workflow.session import AlignmentSession


class WorkflowEvaluator:

    def evaluate_session(self, session: AlignmentSession) -> dict:
        """Computes all metrics for a single alignment session."""
        # Timing metrics — last completed timing per step name wins
        timings = {}
        for t in session.step_timings:
            if t.duration_minutes is not None:
                timings[t.step_name] = t.duration_minutes
        total_alignment_minutes = timings.get("alignment_session")
        ra_review_minutes = timings.get("ra_review")

        # Content revision requests — only content_change type counts
        content_revisions = [
            r for r in session.content_revision_requests
            if r.change_type == "content_change"
        ]

        # Survey aggregates
        surveys = session.survey_responses

        def avg(field):
            vals = [getattr(s, field) for s in surveys if getattr(s, field, None)]
            return round(sum(vals) / len(vals), 1) if vals else None

        return {
            "session_id": session.session_id,
            "simulation_mode": session.simulation_mode,
            "document_type": session.document_type,
            "participants": len(session.participants),
            "roles": [p.role for p in session.participants],

            # Hypothesis 1: EOP2 Alignment
            "alignment_duration_minutes": total_alignment_minutes,
            "ra_review_duration_minutes": ra_review_minutes,
            "gaps_detected": session.gaps_detected,
            "gaps_filled_jit": session.gaps_filled_jit,
            "qc_findings_total": session.qc_findings_total,
            "qc_findings_blocking": session.qc_findings_blocking,
            "review_decisions_total": session.review_decisions_total,
            "content_revision_requests": len(content_revisions),
            "content_revision_rate": round(
                len(content_revisions) / max(len(session.participants), 1), 1
            ),

            # Hypothesis 2: Role-Based Review
            "avg_alignment_process_preference": avg("alignment_process_preference"),
            "avg_spec_quality_rating": avg("spec_quality_rating"),
            "avg_qc_findings_utility": avg("qc_findings_utility"),
            "avg_role_review_clarity": avg("role_review_clarity"),
            "avg_confidence_in_document": avg("confidence_in_document"),
            "avg_likelihood_no_content_revisions": avg("likelihood_of_content_revisions"),
            "survey_completion_rate": round(
                sum(1 for p in session.participants if p.survey_completed)
                / max(len(session.participants), 1), 2
            ),

            # QC pipeline effectiveness
            "qc_catch_rate": self._compute_qc_catch_rate(session),
        }

    def _compute_qc_catch_rate(self, session: AlignmentSession) -> Optional[float]:
        """
        Of all content revision requests raised post-prose-generation, what
        proportion were already flagged by the QC pipeline? A high catch rate
        means the QC pipeline is doing its job.

        Stub: returns None (requires manual adjudication post-session).
        """
        return None

    def compare_modes(
        self,
        high_quality_sessions: list,
        low_quality_sessions: list,
    ) -> dict:
        """
        Compares high_quality vs low_quality simulation outcomes.
        High quality = good content spec → fewer content revisions, higher survey
        scores. The difference validates that spec quality drives workflow outcomes.
        """
        hq_metrics = [self.evaluate_session(s) for s in high_quality_sessions]
        lq_metrics = [self.evaluate_session(s) for s in low_quality_sessions]

        def avg_field(metrics, field):
            vals = [m[field] for m in metrics if m.get(field) is not None]
            return round(sum(vals) / len(vals), 1) if vals else None

        return {
            "high_quality": {
                "sessions": len(hq_metrics),
                "avg_content_revisions": avg_field(hq_metrics, "content_revision_requests"),
                "avg_alignment_minutes": avg_field(hq_metrics, "alignment_duration_minutes"),
                "avg_survey_preference": avg_field(hq_metrics, "avg_alignment_process_preference"),
                "avg_survey_confidence": avg_field(hq_metrics, "avg_confidence_in_document"),
            },
            "low_quality": {
                "sessions": len(lq_metrics),
                "avg_content_revisions": avg_field(lq_metrics, "content_revision_requests"),
                "avg_alignment_minutes": avg_field(lq_metrics, "alignment_duration_minutes"),
                "avg_survey_preference": avg_field(lq_metrics, "avg_alignment_process_preference"),
                "avg_survey_confidence": avg_field(lq_metrics, "avg_confidence_in_document"),
            },
            "delta": {
                "content_revisions": (
                    (avg_field(lq_metrics, "content_revision_requests") or 0)
                    - (avg_field(hq_metrics, "content_revision_requests") or 0)
                ),
                "survey_preference": (
                    (avg_field(hq_metrics, "avg_alignment_process_preference") or 0)
                    - (avg_field(lq_metrics, "avg_alignment_process_preference") or 0)
                ),
            },
            "validation": {
                "high_quality_fewer_revisions": self._lt(
                    avg_field(hq_metrics, "content_revision_requests"),
                    avg_field(lq_metrics, "content_revision_requests"),
                ),
                "high_quality_higher_preference": self._lt(
                    avg_field(lq_metrics, "avg_alignment_process_preference"),
                    avg_field(hq_metrics, "avg_alignment_process_preference"),
                ),
            },
        }

    @staticmethod
    def _lt(a, b) -> bool:
        """None-safe strict less-than; False when either side is missing.
        (Avoids the `x or default` idiom, which mis-handles a legitimate 0.)"""
        if a is None or b is None:
            return False
        return a < b

    def to_dataframe(self, sessions: list) -> pd.DataFrame:
        return pd.DataFrame([self.evaluate_session(s) for s in sessions])
