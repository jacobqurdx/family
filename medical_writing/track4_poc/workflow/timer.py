"""
StepTimer: per-step timing capture for alignment sessions.

Thin wrapper over the session's StepTiming list — the canonical step names used
across the app are defined here so the evaluator and the UI agree.
"""
from workflow.session import AlignmentSession, StepTiming

# Canonical step names (the evaluator keys off these)
SPEC_GENERATION = "spec_generation"
RA_REVIEW = "ra_review"
QC_PIPELINE = "qc_pipeline"
ALIGNMENT_SESSION = "alignment_session"
POST_PROSE_REVIEW = "post_prose_review"


class StepTimer:
    def __init__(self, session: AlignmentSession):
        self._session = session

    def start(self, step_name: str) -> StepTiming:
        return self._session.start_step(step_name)

    def stop(self, step_name: str) -> StepTiming:
        return self._session.complete_step(step_name)

    def get(self, step_name: str) -> StepTiming:
        for t in reversed(self._session.step_timings):
            if t.step_name == step_name:
                return t
        return None

    def duration(self, step_name: str):
        t = self.get(step_name)
        return t.duration_minutes if t else None
