"""
AssignmentLoader: loads DocumentAssignment objects from JSON files.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import List

from workflow.models import DocumentAssignment
import config


class AssignmentLoader:
    def __init__(self, assignments_dir: str = None):
        self._dir = Path(assignments_dir or config.ASSIGNMENTS_DIR)

    def load(self, assignment_id: str) -> DocumentAssignment:
        path = self._dir / f"{assignment_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Assignment not found: {assignment_id}")
        raw = json.loads(path.read_text())
        return DocumentAssignment(**raw)

    def list_assignments(self) -> List[str]:
        return [f.stem for f in sorted(self._dir.glob("*.json"))]

    def load_all(self) -> List[DocumentAssignment]:
        assignments = []
        for aid in self.list_assignments():
            try:
                assignments.append(self.load(aid))
            except Exception:
                pass
        return assignments
