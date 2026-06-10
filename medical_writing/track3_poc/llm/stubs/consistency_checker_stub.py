# PROMOTION SLOT: ConsistencyChecker
# Replace with functional ConsistencyChecker from LLM workstream at Alpha maturity.
# Interface: check(spec: ContentSpec) -> list[QCFinding]
from review.finding_models import QCFinding
import config


class ConsistencyCheckerStub:
    """
    Checks for internal consistency issues within a content specification.
    High quality mode: finds real injected inconsistency (none in clean spec).
    Low quality mode: returns findings to test the review interface.
    """

    def check(self, spec) -> list:
        findings = []
        if config.SIMULATION_MODE == "low_quality":
            findings.append(QCFinding(
                finding_id="con_001",
                section_id="background_rationale",
                pass_number=1,
                severity="major",
                category="internal_inconsistency",
                description="Study phase referenced as 'Phase 2' in background but 'Phase 1b/2' in proposed Phase 3 design section.",
                offending_text="Phase 1b/2",
                role_relevance=["regulatory_affairs", "medical_writing"],
                suggested_resolution="Align study phase terminology across all sections.",
            ))
            findings.append(QCFinding(
                finding_id="con_002",
                section_id="phase2_results_summary",
                pass_number=1,
                severity="minor",
                category="internal_inconsistency",
                description="Primary endpoint timepoint stated as 'Week 36' in results section but 'Week 52' in Phase 3 design section.",
                offending_text="Week 52",
                role_relevance=["clinical_science", "regulatory_affairs"],
                suggested_resolution="Confirm Phase 3 primary endpoint timepoint with clinical science.",
            ))
        return findings
