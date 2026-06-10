"""
FrameworkTwinManager: load / save / query the regulatory framework twin.

The framework twin is the per-agency store of ingested guidance requirements,
known agency concerns, and prior company positions.
"""
from pathlib import Path
from typing import Optional
import json

from regulatory.requirement_models import (
    RegulatoryFrameworkTwin, RegulatoryRequirement,
)
import config


class FrameworkTwinManager:
    def __init__(self, framework_dir: Optional[str] = None):
        self._dir = Path(framework_dir or config.FRAMEWORK_TWINS_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)

    def list_ids(self) -> list:
        return sorted(f.stem for f in self._dir.glob("*.json"))

    def load(self, framework_id: str) -> RegulatoryFrameworkTwin:
        path = self._dir / f"{framework_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Framework twin not found: {framework_id}")
        return RegulatoryFrameworkTwin(**json.loads(path.read_text()))

    def save(self, twin: RegulatoryFrameworkTwin) -> None:
        path = self._dir / f"{twin.framework_id}.json"
        path.write_text(twin.model_dump_json(indent=2))

    def requirements_for(self, framework_id: str, document_type: str) -> list:
        """Requirements that apply to a given document type."""
        twin = self.load(framework_id)
        return [r for r in twin.requirements
                if document_type in r.applies_to_document_types]

    def add_requirements(self, framework_id: str,
                         requirements: list) -> RegulatoryFrameworkTwin:
        """Merge newly-extracted requirements into the framework twin (by id)."""
        twin = self.load(framework_id)
        existing = {r.requirement_id for r in twin.requirements}
        for r in requirements:
            if r.requirement_id not in existing:
                twin.requirements.append(r)
        self.save(twin)
        return twin
