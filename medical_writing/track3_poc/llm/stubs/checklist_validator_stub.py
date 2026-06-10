# PROMOTION SLOT: ChecklistValidator
# No LLM required — rules are explicit. This stub implements the real logic.
# Replace only if checklist evaluation is enhanced with LLM-based rule interpretation.
# Interface: validate(spec: ContentSpec, checklist_path: str) -> list[QCFinding]
from review.finding_models import QCFinding
import json
from pathlib import Path


class ChecklistValidator:
    """
    Runs standing QC rules against the content specification.
    Rules are defined in data/checklists/eop2_checklist.json.
    This is the one QC component that is NOT a stub — rules are explicit.
    """

    def validate(self, spec, checklist_path: str) -> list:
        checklist = json.loads(Path(checklist_path).read_text())
        findings = []
        section_ids = {s.section_id for s in spec.sections}
        for i, rule in enumerate(checklist.get("rules", [])):
            required_section = rule.get("required_section")
            if required_section and required_section not in section_ids:
                findings.append(QCFinding(
                    finding_id=f"chk_{i:03d}",
                    section_id=required_section,
                    pass_number=3,
                    severity=rule.get("severity", "major"),
                    category="checklist_violation",
                    description=rule.get(
                        "description",
                        f"Required section '{required_section}' missing from content specification.",
                    ),
                    role_relevance=rule.get("role_relevance", ["regulatory_affairs"]),
                    suggested_resolution=rule.get("resolution", "Add the required section."),
                ))
        return findings
