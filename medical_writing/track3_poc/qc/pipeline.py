"""
QCPipeline: orchestrates all five QC passes in sequence.

Each pass receives the ContentSpec and adds findings. The pipeline is designed
so functional model components can be promoted in one at a time without
changing the orchestration.

  Pass 1  consistency      internal contradiction detection
  Pass 2  historical       prior CRL / agency-concern check
  Pass 3  checklist        standing rules validation (real logic)
  Pass 4  metacognitive    low-confidence flagging
  Pass 5  role routing     role-based finding routing (V1: all to all)
"""
from typing import Optional

from generation.spec_models import ContentSpec
from review.finding_models import QCFinding
import config


class QCPipeline:
    def __init__(self, framework_twin, checklist_path: str):
        self._framework = framework_twin
        self._checklist_path = checklist_path
        self._load_components()

    def _load_components(self):
        """
        Loads stub or functional components based on USE_STUB config.
        Promotion: replace stub imports with functional model imports here.
        """
        if config.USE_STUB:
            from llm.stubs.consistency_checker_stub import ConsistencyCheckerStub
            from llm.stubs.historical_checker_stub import HistoricalCheckerStub
            from llm.stubs.checklist_validator_stub import ChecklistValidator
            from llm.stubs.metacognitive_stub import MetacognitiveFlaggerStub
            from llm.stubs.role_router_stub import RoleRouterStub
            self._consistency = ConsistencyCheckerStub()
            self._historical = HistoricalCheckerStub()
            self._checklist = ChecklistValidator()
            self._metacognitive = MetacognitiveFlaggerStub()
            self._router = RoleRouterStub()
        else:
            # PROMOTION: import functional components here as they become available
            raise NotImplementedError(
                "Functional QC components not yet promoted. Set USE_STUB=true."
            )

    def run(self, spec: ContentSpec):
        """Run all five passes. Returns (updated_spec, all_findings)."""
        all_findings = []

        # Pass 1: Internal consistency
        all_findings.extend(self._consistency.check(spec))
        # Pass 2: Historical issue check
        all_findings.extend(self._historical.check(spec, self._framework))
        # Pass 3: Checklist validation (real logic)
        all_findings.extend(self._checklist.validate(spec, self._checklist_path))
        # Pass 4: Metacognitive flagging
        all_findings.extend(self._metacognitive.flag(spec))
        # Pass 5: Role-based routing (V1: all findings visible to all roles)
        # all_findings = self._router.route(all_findings, requesting_role)

        blocking = [f for f in all_findings if f.severity == "blocking"]
        spec.qc_passed = len(blocking) == 0
        for section in spec.sections:
            section.qc_findings = [
                f.finding_id for f in all_findings if f.section_id == section.section_id
            ]
        return spec, all_findings
