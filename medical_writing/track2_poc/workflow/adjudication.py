"""
AdjudicationManager: records adjudication decisions for workflow sessions.
"""
from __future__ import annotations
import datetime
from typing import Optional

from workflow.models import (
    WorkflowSession, AdjudicationRecord, AdjudicationDecision,
)


class AdjudicationManager:
    def record_decision(
        self,
        session: WorkflowSession,
        section_id: str,
        section_title: str,
        decision: AdjudicationDecision,
        simulated_prose: str,
        final_prose: str,
        revision_notes: Optional[str] = None,
        time_seconds: float = 0.0,
    ) -> AdjudicationRecord:
        record = AdjudicationRecord(
            section_id=section_id,
            section_title=section_title,
            decision=decision,
            simulated_prose=simulated_prose,
            final_prose=final_prose,
            revision_notes=revision_notes,
            time_seconds=time_seconds,
            adjudicated_at=datetime.datetime.utcnow(),
        )
        # Replace existing record for same section_id, or append
        existing_idx = next(
            (i for i, r in enumerate(session.adjudication_records) if r.section_id == section_id),
            None,
        )
        if existing_idx is not None:
            session.adjudication_records[existing_idx] = record
        else:
            session.adjudication_records.append(record)
        return record

    def get_record(
        self, session: WorkflowSession, section_id: str
    ) -> Optional[AdjudicationRecord]:
        for r in session.adjudication_records:
            if r.section_id == section_id:
                return r
        return None

    def get_approval_rate(self, session: WorkflowSession) -> float:
        if not session.adjudication_records:
            return 0.0
        approved = sum(
            1 for r in session.adjudication_records
            if r.decision == AdjudicationDecision.APPROVED
        )
        return approved / len(session.adjudication_records)
