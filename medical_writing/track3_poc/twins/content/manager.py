"""
ContentTwinManager: CRUD + back-propagation for content twins.

A content twin IS the Track 1 DigitalTwin (the "what we know" store). This
manager adds the regulatory-affairs operations layered on top: loading by id,
listing the store, and writing reviewer-provided / JIT-gap values back with
full provenance.
"""
from pathlib import Path
from typing import Optional
import json

from core.twin import DigitalTwin
from core.models import ElementStatus
import config


class ContentTwinManager:
    def __init__(self, content_dir: Optional[str] = None):
        self._dir = Path(content_dir or config.CONTENT_TWINS_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)

    def list_ids(self) -> list:
        return sorted(f.stem for f in self._dir.glob("*.json"))

    def load(self, twin_id: str) -> DigitalTwin:
        return DigitalTwin.load(twin_id)

    def meta(self, twin_id: str) -> dict:
        """Lightweight metadata read without instantiating the full twin API."""
        raw = json.loads((self._dir / f"{twin_id}.json").read_text())
        return {
            "twin_id": raw.get("twin_id"),
            "tier": raw.get("tier"),
            "program_name": raw.get("program_name"),
            "trial_name": raw.get("trial_name"),
            "parent_twin_id": raw.get("parent_twin_id"),
            "n_elements": len(raw.get("elements", {})),
        }

    def back_propagate(
        self, twin_id: str, element_id: str, value,
        source: str = "jit_gap_fill", modified_by: str = "regulatory_affairs",
    ) -> DigitalTwin:
        """
        Write a reviewer-provided / JIT-gap value to the content twin with
        provenance, then persist. Used by the gap loop and by review
        back-propagation.
        """
        twin = self.load(twin_id)
        twin.set(
            element_id, value,
            source=source,
            status=ElementStatus.VERIFIED,
            modified_by=modified_by,
        )
        twin.save()
        return twin
