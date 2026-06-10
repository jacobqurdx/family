"""
LabelingSession lifecycle + persistence.

The session models (LabelingSession, LabelingSurveyResponse) are defined in
labeling.labeling_models and re-exported here so both
`from workflow.session import LabelingSession` and
`from labeling.labeling_models import LabelingSession` resolve. SessionManager
persists sessions to RESULTS_DIR for the cross-session dashboard.
"""
import json
import datetime
from pathlib import Path
from typing import Optional

from labeling.labeling_models import LabelingSession, LabelingSurveyResponse  # noqa: F401
import config

# Canonical phase order
PHASES = ["setup", "ci_review", "map_review", "qc", "locked", "complete"]


class SessionManager:
    def __init__(self, results_dir: Optional[str] = None):
        self._dir = Path(results_dir or config.RESULTS_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, session: LabelingSession) -> None:
        path = self._dir / f"{session.session_id}.json"
        path.write_text(session.model_dump_json(indent=2))

    def load(self, session_id: str) -> LabelingSession:
        path = self._dir / f"{session_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")
        return LabelingSession(**json.loads(path.read_text()))

    def list_sessions(self) -> list:
        sessions = []
        for f in sorted(self._dir.glob("*.json")):
            try:
                sessions.append(self.load(f.stem))
            except Exception:
                pass
        return sessions


def record_step(session: LabelingSession, step: str) -> dict:
    """Append a timestamped step marker to the session's timing list."""
    entry = {"step": step, "timestamp": datetime.datetime.utcnow().isoformat()}
    session.step_timings.append(entry)
    return entry
