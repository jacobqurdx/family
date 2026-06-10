"""
FeedbackHandler: applies structured reviewer decisions.

Each ReviewDecision is a from→to change on a spec section/claim. When a decision
carries back_propagate=True, the to_value is written to the content twin with
provenance so future documents inherit the correction.
"""
from typing import Optional

from review.finding_models import ReviewDecision
from twins.content.manager import ContentTwinManager


class FeedbackHandler:
    def __init__(self, content_manager: Optional[ContentTwinManager] = None):
        self._content = content_manager or ContentTwinManager()

    def apply(self, content_twin_id: str, decisions: list) -> dict:
        """
        Apply a batch of reviewer decisions. Returns a summary dict with counts
        and the list of element IDs back-propagated to the content twin.

        For the POC, back-propagation maps a decision's section_id to a content
        element of the same name when present; otherwise the section_id is used
        as the element key. Production would resolve the target element from the
        claim's supporting_element_id.
        """
        applied = {"accepted": 0, "corrected": 0, "suggested": 0,
                   "flagged": 0, "overridden": 0, "back_propagated": []}
        for d in decisions:
            if d.decision == "accept":
                applied["accepted"] += 1
            elif d.decision == "correct":
                applied["corrected"] += 1
            elif d.decision == "suggest":
                applied["suggested"] += 1
            elif d.decision == "flag_for_discussion":
                applied["flagged"] += 1
            elif d.decision == "override":
                applied["overridden"] += 1

            if d.back_propagate and d.to_value is not None:
                element_id = d.section_id
                self._content.back_propagate(
                    content_twin_id, element_id, d.to_value,
                    source="review_back_propagation",
                    modified_by=d.reviewer_role,
                )
                applied["back_propagated"].append(element_id)
        return applied
