"""
GapDetector: identifies content-twin elements that a document structure twin
requires but the content twin does not yet populate.

A "gap" is any element listed in a structure twin section's source_elements
that resolves to None (or is absent) in the content twin.
"""
from core.twin import DigitalTwin
from twins.structure.models import DocumentStructureTwin


class GapDetector:
    def detect(self, content_twin: DigitalTwin, structure_twin: DocumentStructureTwin) -> list:
        """Return the de-duplicated list of missing element IDs for the document."""
        gaps = []
        seen = set()
        for section in structure_twin.sections:
            for eid in section.source_elements:
                if eid in seen:
                    continue
                seen.add(eid)
                if content_twin.get_value(eid) is None:
                    gaps.append(eid)
        return gaps

    def detect_by_section(self, content_twin: DigitalTwin,
                          structure_twin: DocumentStructureTwin) -> dict:
        """Return {section_id: [missing element IDs]} for targeted gap asks."""
        out = {}
        for section in structure_twin.sections:
            missing = [eid for eid in section.source_elements
                       if content_twin.get_value(eid) is None]
            if missing:
                out[section.section_id] = missing
        return out
