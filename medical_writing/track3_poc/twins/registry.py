"""
TwinRegistry: resolves the (content twin, structure twin) pair for a document
generation request.

Document generation in Track 3 is always f(Content Twin, Document Structure
Twin) -> Document. The registry is the single place that knows which content
twin feeds which document type. For the POC the mapping is declared explicitly;
in production this would be configuration owned by Regulatory Affairs.
"""
from typing import Optional

from twins.structure.manager import StructureTwinManager
from twins.content.manager import ContentTwinManager
from twins.structure.models import TwinPair
import config

# Document type (short key) -> default content twin id.
# Each structure twin declares its own document_type; this maps the document
# type to the content twin that supplies its facts.
DEFAULT_CONTENT_BY_STRUCTURE = {
    "structure_eop2_fda": "molecule_aleniglipron",
    "structure_ind_fda": "molecule_aleniglipron",
}


class TwinRegistry:
    def __init__(self, default_role: Optional[str] = None):
        self._structures = StructureTwinManager()
        self._content = ContentTwinManager()
        self._role = default_role or config.SESSION_ROLE

    def list_pairs(self) -> list:
        """One TwinPair per available structure twin, paired with its default content twin."""
        pairs = []
        available_content = set(self._content.list_ids())
        for sid in self._structures.list_ids():
            structure = self._structures.load(sid)
            content_id = DEFAULT_CONTENT_BY_STRUCTURE.get(sid)
            if content_id is None or content_id not in available_content:
                # fall back to first content twin if no explicit mapping
                content_id = next(iter(sorted(available_content)), None)
            if content_id is None:
                continue
            pairs.append(TwinPair(
                document_type=structure.document_type,
                content_twin_id=content_id,
                structure_twin_id=sid,
                requesting_role=self._role,
            ))
        return pairs

    def resolve(self, structure_twin_id: str,
                content_twin_id: Optional[str] = None) -> TwinPair:
        """Resolve a concrete pair for a structure twin id."""
        structure = self._structures.load(structure_twin_id)
        content_id = (content_twin_id
                      or DEFAULT_CONTENT_BY_STRUCTURE.get(structure_twin_id)
                      or next(iter(self._content.list_ids()), None))
        return TwinPair(
            document_type=structure.document_type,
            content_twin_id=content_id,
            structure_twin_id=structure_twin_id,
            requesting_role=self._role,
        )

    def get_content_twin(self, content_twin_id: str):
        return self._content.load(content_twin_id)

    def get_structure_twin(self, structure_twin_id: str):
        return self._structures.load(structure_twin_id)
