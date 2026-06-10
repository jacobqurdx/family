"""
Participant helpers: role/timing/decision lifecycle on top of ParticipantRecord.

The record itself lives in workflow/session.py (it is embedded in the session
document); this module owns the state transitions.
"""
import datetime
from typing import Optional

from workflow.session import AlignmentSession, ParticipantRecord


def add_participant(session: AlignmentSession, participant_id: str,
                    role: str) -> ParticipantRecord:
    existing = session.get_participant(role)
    if existing:
        return existing
    record = ParticipantRecord(participant_id=participant_id, role=role)
    session.participants.append(record)
    return record


def start_review(session: AlignmentSession, role: str) -> Optional[ParticipantRecord]:
    p = session.get_participant(role)
    if p and not p.review_started_at:
        p.review_started_at = datetime.datetime.utcnow()
    return p


def complete_review(session: AlignmentSession, role: str,
                    decisions_made: int) -> Optional[ParticipantRecord]:
    p = session.get_participant(role)
    if p:
        p.review_completed_at = datetime.datetime.utcnow()
        p.decisions_made = decisions_made
    session.review_decisions_total += decisions_made
    return p


def review_duration_minutes(p: ParticipantRecord) -> Optional[float]:
    if p.review_started_at and p.review_completed_at:
        delta = p.review_completed_at - p.review_started_at
        return round(delta.total_seconds() / 60, 1)
    return None
