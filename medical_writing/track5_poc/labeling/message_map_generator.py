"""
MessageMapGenerator: generates a draft message map from the CI twin and the
molecule content twin. All LLM functionality is stubbed in Track 5.

The functional model is LLM workstream item LLM-14 (Message Map Generator).
Promotion slot is in _generate_real().
"""
import uuid

from labeling.labeling_models import (
    MessageMap, MessageMapClaim, Achievability,
)
from labeling.ci_twin import CITwinManager
import config


class MessageMapGenerator:
    def __init__(self, use_real_llm: bool = False):
        self._use_real = use_real_llm and bool(config.ANTHROPIC_API_KEY) and not config.USE_STUB
        self._ci_mgr = CITwinManager()

    def generate(self, ci_twin, content_twin, document_type: str = "ccds",
                 requesting_role: str = "regulatory_affairs") -> MessageMap:
        if self._use_real:
            return self._generate_real(ci_twin, content_twin, document_type, requesting_role)
        return self._generate_stub(ci_twin, content_twin, document_type, requesting_role)

    def _generate_stub(self, ci_twin, content_twin, document_type, requesting_role) -> MessageMap:
        # PROMOTION SLOT: LLM-14 (MessageMapGenerator)
        # Replace _generate_real() with the functional LLM-14 implementation
        # from the LLM workstream when it reaches Alpha maturity.
        drug = content_twin.get_value("drug_name") or "aleniglipron"
        indication = content_twin.get_value("indication") or "obesity"
        endpoint = content_twin.get_value("primary_endpoint") or "change from baseline in body weight (%)"
        endpoint_tp = content_twin.get_value("primary_endpoint_timepoint") or "Week 36"
        phase = content_twin.get_value("study_phase") or "Phase 2"

        if config.SIMULATION_MODE == "high_quality":
            return self._high_quality_stub(drug, indication, endpoint, endpoint_tp,
                                           phase, ci_twin, document_type, requesting_role)
        return self._low_quality_stub(drug, indication, endpoint, endpoint_tp,
                                      phase, ci_twin, document_type, requesting_role)

    def _high_quality_stub(self, drug, indication, endpoint, endpoint_tp, phase,
                           ci_twin, document_type, requesting_role) -> MessageMap:
        claims = [
            MessageMapClaim(
                claim_id="claim_001",
                label_section="Indications and Usage",
                proposed_claim_text=(
                    f"{drug.capitalize()} is indicated as an adjunct to a reduced-calorie diet "
                    f"and increased physical activity for chronic weight management in adults "
                    f"with an initial BMI of 30 kg/m2 or greater (obesity), or 27 kg/m2 or greater "
                    f"(overweight) in the presence of at least one weight-related comorbidity."
                ),
                supporting_element_id="indication",
                supporting_value=indication,
                regulatory_precedent_ids=["ap_001", "ap_002", "ap_003"],
                precedent_summary=(
                    "Semaglutide (Wegovy), tirzepatide (Zepbound), and liraglutide (Saxenda) "
                    "all approved with identical BMI thresholds and comorbidity allowance language "
                    "in Indications and Usage. This language is now the class standard for GLP-1 "
                    "agonists and related mechanisms in obesity."
                ),
                achievability=Achievability.HIGH,
                risk_note=(
                    "Language is well-established class standard. Low regulatory risk. FDA may "
                    "scrutinize the mechanism description if it differs meaningfully from the "
                    "GLP-1 receptor agonist class labeling."
                ),
                confidence=0.95,
                confidence_rationale="Direct class precedent from three approved drugs with identical indication language.",
            ),
            MessageMapClaim(
                claim_id="claim_002",
                label_section="Clinical Studies",
                proposed_claim_text=(
                    f"In the ACCESS II trial, {drug.capitalize()}-treated patients achieved a "
                    f"statistically significant reduction in body weight at {endpoint_tp} compared "
                    f"to placebo. [Specific result values to be confirmed from final CSR.]"
                ),
                supporting_element_id="primary_endpoint_result",
                supporting_value=None,
                regulatory_precedent_ids=["ap_006", "ap_007"],
                precedent_summary=(
                    "Semaglutide and tirzepatide Phase 3 data presented as mean percent change "
                    "from baseline with 95% CI and p-value in Clinical Studies. FDA expects the "
                    "placebo-subtracted effect size prominently displayed."
                ),
                achievability=Achievability.MEDIUM,
                risk_note=(
                    "Phase 2 data only at this stage. FDA will require Phase 3 pivotal data before "
                    "approving Clinical Studies label language. This claim is a placeholder for NDA "
                    "preparation — not appropriate for current regulatory interactions."
                ),
                confidence=0.75,
                confidence_rationale="Precedent strong; Phase 2 data not sufficient for final label language.",
                is_gap=True,
            ),
            MessageMapClaim(
                claim_id="claim_003",
                label_section="Clinical Studies",
                proposed_claim_text=(
                    f"In ACCESS II, [X]% of {drug.capitalize()}-treated patients achieved at least "
                    f"5% reduction in body weight at {endpoint_tp} compared to [Y]% of "
                    f"placebo-treated patients."
                ),
                supporting_element_id="responder_analysis_5pct",
                supporting_value=None,
                regulatory_precedent_ids=["ap_006", "ap_007"],
                precedent_summary=(
                    "Responder analysis (>=5% and >=10% weight loss) is consistently presented in "
                    "Clinical Studies for all approved obesity drugs. FDA guidance explicitly "
                    "requires this analysis. Semaglutide label shows ~83% >=5% responders vs ~32% placebo."
                ),
                achievability=Achievability.HIGH,
                risk_note=(
                    "Responder analysis is a mandatory FDA requirement per obesity guidance. Risk "
                    "is low on inclusion; risk is in the magnitude — if our responder rate is "
                    "substantially below semaglutide and tirzepatide, expect FDA questions on "
                    "comparative effectiveness."
                ),
                confidence=0.80,
                confidence_rationale="Mandatory FDA requirement with strong precedent; values TBD from Phase 3.",
                is_gap=True,
            ),
            MessageMapClaim(
                claim_id="claim_004",
                label_section="Warnings and Precautions",
                proposed_claim_text=(
                    f"Risk of thyroid C-cell tumors: {drug.capitalize()}, like other GLP-1 receptor "
                    f"agonists, causes dose-dependent and treatment-duration-dependent thyroid C-cell "
                    f"tumors in rodents. It is unknown whether {drug.capitalize()} causes thyroid "
                    f"C-cell tumors, including medullary thyroid carcinoma (MTC), in humans."
                ),
                supporting_element_id="mechanism_of_action",
                supporting_value="GLP-1 receptor agonist",
                regulatory_precedent_ids=["ap_008", "ap_009"],
                precedent_summary=(
                    "Identical thyroid C-cell tumor warning required for all GLP-1 receptor agonists "
                    "as a class effect. Semaglutide and tirzepatide carry this warning verbatim. "
                    "FDA will require this language."
                ),
                achievability=Achievability.HIGH,
                risk_note=(
                    "This is a mandatory class-effect warning. Not achieving this language is not an "
                    "option — it must appear. Risk is in characterization: if aleniglipron has "
                    "different nonclinical thyroid findings, language may need to be strengthened."
                ),
                confidence=0.92,
                confidence_rationale="Mandatory class-effect warning. Language is effectively fixed by class precedent.",
                back_propagate=True,
            ),
            MessageMapClaim(
                claim_id="claim_005",
                label_section="Adverse Reactions",
                proposed_claim_text=(
                    f"The most common adverse reactions (incidence >=5% and greater than placebo) in "
                    f"{drug.capitalize()}-treated patients were: nausea, diarrhea, vomiting, "
                    f"constipation, abdominal pain. [Specific incidence rates to be confirmed from "
                    f"final integrated safety summary.]"
                ),
                supporting_element_id="adverse_reactions_summary",
                supporting_value=None,
                regulatory_precedent_ids=["ap_011", "ap_012"],
                precedent_summary=(
                    "GI adverse reactions (nausea, diarrhea, vomiting, constipation, abdominal pain) "
                    "are the class-defining AE profile for GLP-1 agonists. All approved labels list "
                    "these as most common ARs at broadly similar incidence rates."
                ),
                achievability=Achievability.HIGH,
                risk_note=(
                    "GI AE profile is expected and well-precedented. Risk is in the incidence rates "
                    "— if aleniglipron's GI rates are materially higher than semaglutide/tirzepatide, "
                    "FDA may require enhanced GI safety language. ISS data required to confirm rates."
                ),
                confidence=0.78,
                confidence_rationale="AE type well-established; specific rates require ISS data.",
                is_gap=True,
            ),
        ]

        m = MessageMap(
            map_id=f"map_{uuid.uuid4().hex[:8]}",
            program_name="Aleniglipron",
            indication=indication,
            document_type=document_type,
            regulatory_body="FDA",
            ci_twin_id=ci_twin.ci_twin_id,
            content_twin_id="molecule_aleniglipron",
            generated_by_role=requesting_role,
            claims=claims,
        )
        m.recount()
        return m

    def _low_quality_stub(self, drug, indication, endpoint, endpoint_tp, phase,
                          ci_twin, document_type, requesting_role) -> MessageMap:
        """Low quality: poor achievability ratings and missing precedent citations,
        to test the QC pipeline and reviewer experience."""
        m = self._high_quality_stub(drug, indication, endpoint, endpoint_tp, phase,
                                    ci_twin, document_type, requesting_role)
        for claim in m.claims:
            claim.achievability = Achievability.MEDIUM
            claim.regulatory_precedent_ids = []
            claim.precedent_summary = "No competitive precedent identified."
            claim.confidence = 0.40
            claim.risk_note = "Achievability uncertain — precedent not found."
        m.recount()
        return m

    def _generate_real(self, ci_twin, content_twin, document_type, requesting_role) -> MessageMap:
        # PROMOTION SLOT: LLM-14 full implementation
        raise NotImplementedError(
            "LLM-14 functional model not yet promoted. Set USE_STUB=true."
        )
