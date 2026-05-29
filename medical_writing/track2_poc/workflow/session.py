"""
WorkflowSessionManager: create, load, save, and list workflow sessions.
"""
from __future__ import annotations
import json
import uuid
import datetime
from pathlib import Path
from typing import List, Optional

from workflow.models import WorkflowSession
import config


class WorkflowSessionManager:
    def __init__(self, sessions_dir: Optional[str] = None):
        self._dir = Path(sessions_dir or f"{config.SESSIONS_DIR}/workflow")
        self._dir.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        writer_id: str,
        assignment_id: str,
        twin_id: str,
        simulation_mode: str = "high_quality",
    ) -> WorkflowSession:
        session_id = str(uuid.uuid4())[:8]
        session = WorkflowSession(
            session_id=session_id,
            writer_id=writer_id,
            assignment_id=assignment_id,
            twin_id=twin_id,
            simulation_mode=simulation_mode,
            started_at=datetime.datetime.utcnow(),
        )
        self.save(session)
        return session

    def save(self, session: WorkflowSession) -> None:
        path = self._dir / f"{session.session_id}.json"
        path.write_text(session.model_dump_json(indent=2))

    def load(self, session_id: str) -> WorkflowSession:
        path = self._dir / f"{session_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Workflow session not found: {session_id}")
        raw = json.loads(path.read_text())
        return WorkflowSession(**raw)

    def list_sessions(self) -> List[WorkflowSession]:
        sessions = []
        for f in sorted(self._dir.glob("*.json")):
            try:
                sessions.append(self.load(f.stem))
            except Exception:
                pass
        return sessions

    def complete(self, session: WorkflowSession) -> None:
        session.status = "complete"
        session.completed_at = datetime.datetime.utcnow()
        self.save(session)

    def get_summary(self, session: WorkflowSession) -> dict:
        return {
            "session_id": session.session_id,
            "writer_id": session.writer_id,
            "assignment_id": session.assignment_id,
            "twin_id": session.twin_id,
            "simulation_mode": session.simulation_mode,
            "status": session.status,
            "sections_adjudicated": len(session.adjudication_records),
            "started_at": str(session.started_at),
            "completed_at": str(session.completed_at) if session.completed_at else None,
        }
