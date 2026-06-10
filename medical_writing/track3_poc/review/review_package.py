"""
ReviewPackageBuilder: assembles the role-specific review bundle for a single
reviewer from a ContentSpec and its QC findings.

V1 routing: all findings are visible to all roles (RoleRouter is a pass-through
stub). The reviewer's primary_sections come from the role→section map and tell
the UI which sections to expand and star for that reviewer.
"""
import uuid
from typing import Optional

from review.finding_models import ReviewPackage
from llm.stubs.role_router_stub import RoleRouterStub


class ReviewPackageBuilder:
    def __init__(self):
        self._router = RoleRouterStub()

    def build(self, spec, findings: list, role: str) -> ReviewPackage:
        all_findings = list(findings or [])
        role_findings = self._router.route(all_findings, role)
        primary = self._router.get_primary_sections(role)
        return ReviewPackage(
            package_id=f"pkg_{uuid.uuid4().hex[:6]}",
            spec_id=spec.spec_id,
            reviewer_role=role,
            primary_sections=primary,
            all_findings=all_findings,
            role_findings=role_findings,
        )
