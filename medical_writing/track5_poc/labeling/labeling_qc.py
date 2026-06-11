"""
LabelingQCValidator: runs the standing labeling checklist against a MessageMap.

This is the labeling analogue of Track 3's ChecklistValidator, but labeling rules
are keyed off *claim type* (and, for mandatory class claims, precedent grounding)
rather than mere section presence — that is what actually distinguishes a
defensible message map from a weak one. It emits the shared QCFinding model so
the rest of the QC/review tooling is reused unchanged.

Rule satisfaction:
  - thyroid_cCell_warning / indication_bmi_threshold / responder_analysis_5pct:
      a claim in the required section whose text matches the rule keyword AND
      carries competitive precedent (regulatory_precedent_ids non-empty).
      In low_quality mode the generator strips precedent, so the mandatory
      class claims become ungrounded → findings fire.
  - numeric_traceability: any Clinical Studies claim still flagged is_gap.
  - no_promotional_language: any claim text containing promotional terms.
"""
import json
from pathlib import Path

from review.finding_models import QCFinding
import config

# Map human-readable label sections to message-map section keys
_SECTION_KEY = {
    "Warnings and Precautions": "warnings_precautions",
    "Indications and Usage": "indications_usage",
    "Clinical Studies": "clinical_studies",
    "Adverse Reactions": "adverse_reactions",
    "all": "all",
}

_PROMOTIONAL_TERMS = [
    "breakthrough", "best-in-class", "unprecedented", "revolutionary",
    "superior to all", "miracle", "game-changing", "first and only",
]


class LabelingQCValidator:
    def validate(self, message_map, checklist_path: str = None) -> list:
        checklist_path = checklist_path or f"{config.CHECKLISTS_DIR}/labeling_checklist.json"
        checklist = json.loads(Path(checklist_path).read_text())
        findings = []
        claims = message_map.claims

        for rule in checklist.get("rules", []):
            ctype = rule.get("required_claim_type")
            section = rule.get("required_section", "all")
            handler = getattr(self, f"_check_{ctype}", None)
            satisfied = handler(claims) if handler else True
            if not satisfied:
                findings.append(QCFinding(
                    finding_id=rule["rule_id"],
                    section_id=_SECTION_KEY.get(section, section),
                    pass_number=3,
                    severity=rule.get("severity", "major"),
                    category="checklist_violation",
                    description=rule.get("description", ""),
                    role_relevance=rule.get("role_relevance", ["regulatory_affairs"]),
                    suggested_resolution=rule.get("resolution", ""),
                ))
        return findings

    # ── Rule handlers (return True when the rule is satisfied) ─────────────────

    @staticmethod
    def _grounded(claim) -> bool:
        return bool(claim.regulatory_precedent_ids)

    def _check_thyroid_cCell_warning(self, claims) -> bool:
        return any(
            "thyroid c-cell" in c.proposed_claim_text.lower() and self._grounded(c)
            for c in claims
        )

    def _check_indication_bmi_threshold(self, claims) -> bool:
        return any(
            "bmi of 30" in c.proposed_claim_text.lower() and self._grounded(c)
            for c in claims
        )

    def _check_responder_analysis_5pct(self, claims) -> bool:
        return any(
            "5%" in c.proposed_claim_text and self._grounded(c)
            for c in claims
            if c.label_section == "Clinical Studies"
        )

    def _check_numeric_traceability(self, claims) -> bool:
        # Satisfied only if no Clinical Studies claim is still an unfilled gap
        return not any(
            c.is_gap for c in claims if c.label_section == "Clinical Studies"
        )

    def _check_no_promotional_language(self, claims) -> bool:
        for c in claims:
            text = c.proposed_claim_text.lower()
            if any(term in text for term in _PROMOTIONAL_TERMS):
                return False
        return True
