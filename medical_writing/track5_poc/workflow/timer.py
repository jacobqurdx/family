"""
StepTimer: timestamp markers for a labeling session.

Track 5 stores timings as a list of {"step", "timestamp"} dicts on the session
(timestamps are ISO strings). The canonical step names are defined here so the
evaluator and UI agree.
"""
import datetime

from labeling.labeling_models import LabelingSession

# Canonical step markers
CI_REVIEW_COMPLETE = "ci_review_complete"
MAP_GENERATION_START = "map_generation_start"
MAP_GENERATION_COMPLETE = "map_generation_complete"
MAP_LOCKED = "map_locked"


class StepTimer:
    def __init__(self, session: LabelingSession):
        self._session = session

    def mark(self, step: str) -> dict:
        entry = {"step": step, "timestamp": datetime.datetime.utcnow().isoformat()}
        self._session.step_timings.append(entry)
        return entry

    def timestamp(self, step: str):
        for t in self._session.step_timings:
            if t["step"] == step:
                return t["timestamp"]
        return None
