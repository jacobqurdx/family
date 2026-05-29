"""
StepTimer: context manager that measures elapsed time for a workflow step.
"""
from __future__ import annotations
import datetime
import time
from typing import Optional

from workflow.models import WorkflowSession, StepTiming


class StepTimer:
    """
    Context manager usage:
        with StepTimer(session, "section_001", "adjudication") as t:
            ... do work ...
        # t.duration_seconds is now set
    """

    def __init__(
        self,
        session: WorkflowSession,
        step_id: str,
        step_type: str,
    ):
        self._session = session
        self._step_id = step_id
        self._step_type = step_type
        self._start_time: Optional[float] = None
        self.timing: Optional[StepTiming] = None

    def __enter__(self) -> "StepTimer":
        self._start_time = time.monotonic()
        self.timing = StepTiming(
            step_id=self._step_id,
            step_type=self._step_type,
            started_at=datetime.datetime.utcnow(),
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self._start_time is not None and self.timing is not None:
            elapsed = time.monotonic() - self._start_time
            self.timing.duration_seconds = elapsed
            self.timing.completed_at = datetime.datetime.utcnow()
            self._session.timings.append(self.timing)
        return False  # do not suppress exceptions

    @property
    def duration_seconds(self) -> Optional[float]:
        return self.timing.duration_seconds if self.timing else None


class ManualTimer:
    """
    For Streamlit UX where start/stop happen at different page renders.
    Records explicit start/stop datetimes and computes duration.
    """

    def __init__(self, session: WorkflowSession, step_id: str, step_type: str):
        self._session = session
        self._step_id = step_id
        self._step_type = step_type
        self._started_at: Optional[datetime.datetime] = None

    def start(self) -> datetime.datetime:
        self._started_at = datetime.datetime.utcnow()
        return self._started_at

    def stop(self) -> Optional[StepTiming]:
        if self._started_at is None:
            return None
        now = datetime.datetime.utcnow()
        duration = (now - self._started_at).total_seconds()
        timing = StepTiming(
            step_id=self._step_id,
            step_type=self._step_type,
            started_at=self._started_at,
            completed_at=now,
            duration_seconds=duration,
        )
        self._session.timings.append(timing)
        return timing
