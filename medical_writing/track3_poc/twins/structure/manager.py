"""
StructureTwinManager: CRUD + locking for document structure twins.

Document structure twins live as JSON under STRUCTURE_TWINS_DIR. Each is the
blueprint for one document type per regulatory body.
"""
from pathlib import Path
from typing import Optional
import json
import datetime

from twins.structure.models import DocumentStructureTwin
import config


class StructureTwinManager:
    def __init__(self, structure_dir: Optional[str] = None):
        self._dir = Path(structure_dir or config.STRUCTURE_TWINS_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)

    def list_ids(self) -> list:
        return sorted(f.stem for f in self._dir.glob("*.json"))

    def list_all(self) -> list:
        return [self.load(sid) for sid in self.list_ids()]

    def load(self, structure_id: str) -> DocumentStructureTwin:
        path = self._dir / f"{structure_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Structure twin not found: {structure_id}")
        return DocumentStructureTwin(**json.loads(path.read_text()))

    def save(self, twin: DocumentStructureTwin) -> None:
        path = self._dir / f"{twin.structure_id}.json"
        path.write_text(twin.model_dump_json(indent=2))

    def validate(self, twin: DocumentStructureTwin) -> list:
        """Return a list of validation errors. Empty = valid."""
        errors = []
        if not twin.sections:
            errors.append("Structure twin has no sections.")
        seen_orders = {}
        for s in twin.sections:
            if not s.source_elements:
                errors.append(f"Section '{s.section_id}' has no source_elements.")
            if s.ordering in seen_orders:
                errors.append(
                    f"Duplicate ordering {s.ordering}: "
                    f"'{s.section_id}' and '{seen_orders[s.ordering]}'."
                )
            seen_orders[s.ordering] = s.section_id
        return errors

    def lock(self, structure_id: str, locked_by: str) -> DocumentStructureTwin:
        twin = self.load(structure_id)
        twin.locked = True
        twin.locked_at = datetime.datetime.utcnow()
        twin.locked_by = locked_by
        self.save(twin)
        return twin
