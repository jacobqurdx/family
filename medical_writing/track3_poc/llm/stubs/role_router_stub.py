# PROMOTION SLOT: RoleRouter
# Replace with functional role-filtered review router from LLM workstream.
# V1: all findings routed to all roles. Role filtering is a post-launch feature.
# Interface: route(findings: list[QCFinding], role: str) -> list[QCFinding]
from review.finding_models import QCFinding


class RoleRouterStub:
    """
    V1 stub: returns all findings regardless of role.
    Role filtering logic is defined but not applied in V1.
    """

    ROLE_SECTION_MAP = {
        "regulatory_affairs": ["background_rationale", "proposed_phase3_design", "cardiovascular_safety", "regulatory_questions"],
        "clinical_science": ["phase2_results_summary", "proposed_phase3_design"],
        "clinical_operations": ["proposed_phase3_design"],
        "medical_writing": ["background_rationale", "phase2_results_summary", "proposed_phase3_design", "cardiovascular_safety"],
        "biostatistician": ["phase2_results_summary", "proposed_phase3_design"],
    }

    def route(self, findings: list, role: str) -> list:
        # V1: return all findings; role filtering deferred to post-launch
        return findings

    def get_primary_sections(self, role: str) -> list:
        return self.ROLE_SECTION_MAP.get(role, [])
