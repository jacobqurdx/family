# PROMOTION SLOT: MetacognitiveFlagger
# Replace with functional confidence-calibrated MetacognitiveFlagger
# from LLM workstream at Beta maturity.
# Interface: flag(spec: ContentSpec) -> list[QCFinding]
from review.finding_models import QCFinding


class MetacognitiveFlaggerStub:
    """
    Identifies sections where the system's confidence is low and explicit human
    review is required before the spec can be locked.
    """

    def flag(self, spec) -> list:
        findings = []
        for section in spec.sections:
            if section.needs_human_review or section.overall_confidence < 0.75:
                findings.append(QCFinding(
                    finding_id=f"meta_{section.section_id}",
                    section_id=section.section_id,
                    pass_number=4,
                    severity="minor",
                    category="low_confidence",
                    description=(
                        f"Section '{section.section_title}' has overall confidence "
                        f"{section.overall_confidence:.0%}. Human review required before locking."
                    ),
                    role_relevance=section.role_primary,
                    suggested_resolution=(
                        "Review all claims in this section and confirm or correct before "
                        "locking the content specification."
                    ),
                ))
        return findings
