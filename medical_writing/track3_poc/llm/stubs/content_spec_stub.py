# PROMOTION SLOT: ContentSpecGenerator
# Replace with functional ContentSpecGenerator from LLM workstream at Alpha maturity.
# Interface: generate(twin_pair: TwinPair, content_twin: DigitalTwin,
#                     structure_twin: DocumentStructureTwin) -> ContentSpec
from generation.spec_models import ContentSpec, SpecSection, SpecClaim
import config
import uuid


class ContentSpecGeneratorStub:
    def generate(self, twin_pair, content_twin, structure_twin) -> ContentSpec:
        if config.SIMULATION_MODE == "low_quality":
            return self._low_quality_spec(twin_pair, content_twin, structure_twin)
        return self._high_quality_spec(twin_pair, content_twin, structure_twin)

    def _high_quality_spec(self, twin_pair, content_twin, structure_twin) -> ContentSpec:
        drug = content_twin.get_value("drug_name") or "aleniglipron"
        indication = content_twin.get_value("indication") or "obesity"
        phase = content_twin.get_value("study_phase") or "Phase 2"
        endpoint = content_twin.get_value("primary_endpoint") or "change from baseline in body weight (%)"

        sections = [
            SpecSection(
                section_id="background_rationale",
                section_title="Background and Rationale",
                required=True,
                role_primary=["regulatory_affairs", "clinical_science"],
                overall_confidence=0.88,
                claims=[
                    SpecClaim(
                        claim_id="cl_001",
                        claim_text=(
                            f"{drug} is a GLP-1 receptor agonist under investigation for the "
                            f"treatment of {indication}. The {phase} ACCESS II study demonstrated "
                            f"[primary efficacy results to be confirmed]."
                        ),
                        supporting_element_id="drug_name",
                        supporting_value=drug,
                        confidence=0.92,
                        confidence_rationale="Drug name confirmed in content twin.",
                        regulatory_authority="FDA Obesity Guidance Section 2.1",
                    ),
                ],
            ),
            SpecSection(
                section_id="phase2_results_summary",
                section_title="Summary of Phase 2 Results",
                required=True,
                role_primary=["clinical_science", "regulatory_affairs"],
                overall_confidence=0.75,
                needs_human_review=True,
                claims=[
                    SpecClaim(
                        claim_id="cl_002",
                        claim_text=(
                            f"The primary endpoint — {endpoint} at Week 36 — was met with "
                            f"statistical significance. [Specific result values to be confirmed "
                            f"from CSR data.]"
                        ),
                        supporting_element_id="primary_endpoint",
                        supporting_value=endpoint,
                        confidence=0.75,
                        confidence_rationale="Endpoint confirmed; efficacy magnitude not yet in content twin.",
                        is_gap=True,
                        regulatory_authority="FDA Obesity Guidance Section 4.2",
                    ),
                ],
            ),
            SpecSection(
                section_id="proposed_phase3_design",
                section_title="Proposed Phase 3 Design",
                required=True,
                role_primary=["regulatory_affairs", "clinical_science"],
                overall_confidence=0.82,
                claims=[
                    SpecClaim(
                        claim_id="cl_003",
                        claim_text=(
                            f"The proposed Phase 3 program (ACCESS III) will evaluate {drug} in "
                            f"adults with {indication} using a randomized double-blind "
                            f"placebo-controlled parallel-group design. [Sample size justification "
                            f"to be confirmed by biostatistics.]"
                        ),
                        supporting_element_id="indication",
                        supporting_value=indication,
                        confidence=0.82,
                        confidence_rationale="Indication confirmed; Phase 3 sample size pending biostatistics input.",
                        is_gap=True,
                        regulatory_authority="FDA Obesity Guidance Section 6.0",
                    ),
                ],
            ),
            SpecSection(
                section_id="cardiovascular_safety",
                section_title="Cardiovascular Safety Plan",
                required=True,
                role_primary=["regulatory_affairs", "clinical_science"],
                overall_confidence=0.70,
                needs_human_review=True,
                claims=[
                    SpecClaim(
                        claim_id="cl_004",
                        claim_text=(
                            "A comprehensive cardiovascular safety monitoring plan will be "
                            "implemented in Phase 3, including pre-specified monitoring of heart "
                            "rate, blood pressure, and adjudicated MACE events. [Specific CV "
                            "safety data from ACCESS II to be inserted.]"
                        ),
                        supporting_element_id="cv_safety_data",
                        supporting_value=None,
                        confidence=0.70,
                        confidence_rationale="CV safety requirement confirmed from guidance; Phase 2 CV data not yet in content twin.",
                        is_gap=True,
                        regulatory_authority="FDA Obesity Guidance Section 5.1",
                    ),
                ],
            ),
            SpecSection(
                section_id="regulatory_questions",
                section_title="Specific Regulatory Questions",
                required=True,
                role_primary=["regulatory_affairs"],
                overall_confidence=0.85,
                claims=[
                    SpecClaim(
                        claim_id="cl_005",
                        claim_text=(
                            "1. Does the FDA agree with the proposed Phase 3 primary endpoint and "
                            "timepoint? 2. Does the FDA agree the proposed cardiovascular safety "
                            "monitoring plan is adequate? 3. Does the FDA agree with the proposed "
                            "Phase 3 sample size and follow-up duration?"
                        ),
                        supporting_element_id="regulatory_questions_list",
                        supporting_value=None,
                        confidence=0.85,
                        confidence_rationale="Standard EOP2 question set generated; requires RA confirmation.",
                        is_gap=True,
                        regulatory_authority="FDA EOP2 Meeting Guidance 2019, Section 1",
                    ),
                ],
            ),
        ]
        gaps = ["phase2_primary_result", "phase3_sample_size", "cv_safety_data"]
        return ContentSpec(
            spec_id=f"spec_{uuid.uuid4().hex[:8]}",
            document_type="eop2_briefing",
            content_twin_id=twin_pair.content_twin_id,
            structure_twin_id=twin_pair.structure_twin_id,
            generated_by_role=twin_pair.requesting_role,
            sections=sections,
            gaps_detected=gaps,
            version="draft",
        )

    def _low_quality_spec(self, twin_pair, content_twin, structure_twin) -> ContentSpec:
        spec = self._high_quality_spec(twin_pair, content_twin, structure_twin)
        for section in spec.sections:
            for claim in section.claims:
                claim.confidence = 0.40
                claim.confidence_rationale = "Low quality stub: confidence degraded for QC testing."
            section.overall_confidence = 0.40
            section.needs_human_review = True
        return spec
