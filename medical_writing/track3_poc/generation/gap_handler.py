"""
GapHandler: the just-in-time content gap loop.

When the content spec generator encounters a required element missing from the
content twin, the writer is asked for the value. GapHandler applies that value
to the spec (filling the relevant claim) and, on confirmation, back-propagates
it to the content twin with full provenance so future documents inherit it.
"""
from typing import Optional

from generation.spec_models import ContentSpec
from twins.content.manager import ContentTwinManager


class GapHandler:
    def __init__(self, content_manager: Optional[ContentTwinManager] = None):
        self._content = content_manager or ContentTwinManager()

    def fill_gap(
        self,
        spec: ContentSpec,
        element_id: str,
        value,
        filled_by: str = "regulatory_affairs",
        back_propagate: bool = False,
    ) -> ContentSpec:
        """
        Fill a single content gap in the spec.

        - Removes element_id from spec.gaps_detected and records it in gaps_filled.
        - Updates any claim whose supporting_element_id matches: sets the value,
          clears is_gap, records gap_filled_by.
        - If back_propagate, writes the value to the content twin with
          source="jit_gap_fill" so subsequent generations no longer flag it.
        """
        if element_id in spec.gaps_detected:
            spec.gaps_detected = [g for g in spec.gaps_detected if g != element_id]
        if element_id not in spec.gaps_filled:
            spec.gaps_filled.append(element_id)

        for section in spec.sections:
            for claim in section.claims:
                if claim.supporting_element_id == element_id:
                    claim.supporting_value = value
                    claim.is_gap = False
                    claim.gap_filled_by = filled_by

        if back_propagate:
            self._content.back_propagate(
                spec.content_twin_id, element_id, value,
                source="jit_gap_fill", modified_by=filled_by,
            )
        return spec
