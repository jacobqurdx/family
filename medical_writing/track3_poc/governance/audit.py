"""
AuditTrail: simulated change log for the POC.

Records review decisions and lock events with role + timestamp. In production
this would be an append-only, cryptographically-signed 21 CFR Part 11 audit
trail; here it is an in-memory / JSON list.
"""
import datetime
from typing import Optional


class AuditTrail:
    def __init__(self):
        self._entries = []

    def record(self, action: str, role: str, target: str,
               detail: Optional[str] = None, timestamp: Optional[str] = None):
        self._entries.append({
            "action": action,
            "role": role,
            "target": target,
            "detail": detail or "",
            "timestamp": timestamp or datetime.datetime.utcnow().isoformat(),
        })
        return self._entries[-1]

    def record_decisions(self, decisions: list):
        for d in decisions:
            self.record(
                action=f"review_decision:{d.decision}",
                role=d.reviewer_role,
                target=d.section_id,
                detail=(d.to_value or "")[:120],
                timestamp=d.decided_at.isoformat(),
            )
        return self._entries

    def entries(self) -> list:
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)
