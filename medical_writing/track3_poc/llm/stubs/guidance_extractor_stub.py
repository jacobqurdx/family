# PROMOTION SLOT: GuidanceExtractor
# Replace this stub with the functional GuidanceExtractor from the LLM workstream
# when it reaches Alpha maturity (passes eval harness at minimum threshold).
# Interface: extract_requirements(guidance_text: str, document_type: str) -> list[RegulatoryRequirement]
from regulatory.requirement_models import RegulatoryRequirement
import config


class GuidanceExtractorStub:
    """
    Stub for the FDA/EMA guidance ingestion LLM component.
    Returns synthetic but realistic RegulatoryRequirement objects for the FDA
    obesity guidance, EOP2 document type.
    """

    def extract_requirements(
        self, guidance_text: str, document_type: str
    ) -> list:
        if config.SIMULATION_MODE == "low_quality":
            return self._low_quality_requirements()
        return self._high_quality_requirements()

    def _high_quality_requirements(self) -> list:
        return [
            RegulatoryRequirement(
                requirement_id="req_001",
                guidance_document_id="fda_obesity_guidance_2023",
                guidance_section="Section 3.1 — Clinical Trial Design",
                source_quote="Sponsors should include a randomized, double-blind, placebo-controlled trial design for Phase 2 obesity studies.",
                requirement_text="Phase 2 obesity trials must use randomized double-blind placebo-controlled design.",
                applies_to_document_types=["eop2_briefing", "ind"],
                applies_to_indications=["obesity"],
                requirement_type="content",
                mandatory=True,
                confidence=0.95,
            ),
            RegulatoryRequirement(
                requirement_id="req_002",
                guidance_document_id="fda_obesity_guidance_2023",
                guidance_section="Section 4.2 — Endpoints",
                source_quote="The primary endpoint for obesity trials should be percent change from baseline in body weight.",
                requirement_text="Primary endpoint must be percent change from baseline in body weight.",
                applies_to_document_types=["eop2_briefing", "protocol", "csr"],
                applies_to_indications=["obesity"],
                requirement_type="content",
                mandatory=True,
                confidence=0.98,
            ),
            RegulatoryRequirement(
                requirement_id="req_003",
                guidance_document_id="fda_obesity_guidance_2023",
                guidance_section="Section 4.2 — Endpoints",
                source_quote="A weight loss threshold responder analysis (proportion achieving >=5% weight loss) should be included as a key secondary endpoint.",
                requirement_text="Key secondary endpoint: proportion of patients achieving >=5% body weight loss.",
                applies_to_document_types=["eop2_briefing", "protocol"],
                applies_to_indications=["obesity"],
                requirement_type="content",
                mandatory=False,
                confidence=0.92,
            ),
            RegulatoryRequirement(
                requirement_id="req_004",
                guidance_document_id="fda_obesity_guidance_2023",
                guidance_section="Section 5.1 — Safety",
                source_quote="Cardiovascular safety must be addressed, including monitoring for heart rate, blood pressure, and MACE events.",
                requirement_text="EOP2 package must address cardiovascular safety monitoring plan.",
                applies_to_document_types=["eop2_briefing"],
                applies_to_indications=["obesity", "glp1_agonist"],
                requirement_type="content",
                mandatory=True,
                confidence=0.97,
            ),
            RegulatoryRequirement(
                requirement_id="req_005",
                guidance_document_id="fda_obesity_guidance_2023",
                guidance_section="Section 6.0 — Phase 3 Design",
                source_quote="The EOP2 briefing document should include a detailed description of the proposed Phase 3 design including sample size justification.",
                requirement_text="EOP2 briefing document must include proposed Phase 3 design with sample size justification.",
                applies_to_document_types=["eop2_briefing"],
                applies_to_indications=["obesity"],
                requirement_type="structure",
                mandatory=True,
                confidence=0.99,
            ),
        ]

    def _low_quality_requirements(self) -> list:
        reqs = self._high_quality_requirements()
        # Deliberately introduce low confidence and missing citations
        for req in reqs:
            req.confidence = 0.45
            req.source_quote = ""
        return reqs
