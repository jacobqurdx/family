"""
LabelDraftGenerator: generates CCDS section prose from a locked message map.
Reuses the LLM-01 (prose generator) infrastructure with labeling-specific
prompts. Stubbed in the Track 5 POC (LLM-15).
"""
import uuid

from labeling.draft_models import LabelDraft, LabelSection
from labeling.labeling_models import MessageMap
import config


class LabelDraftGenerator:
    def __init__(self, use_real_llm: bool = False):
        self._use_real = use_real_llm and bool(config.ANTHROPIC_API_KEY) and not config.USE_STUB

    def generate(self, message_map: MessageMap) -> LabelDraft:
        if not message_map.locked:
            raise ValueError("Message map must be locked before draft generation.")
        if self._use_real:
            return self._generate_real(message_map)
        return self._generate_stub(message_map)

    def _generate_stub(self, message_map: MessageMap) -> LabelDraft:
        # PROMOTION SLOT: LLM-15 (LabelDraftGenerator)
        # Replace with functional label prose generator from the LLM workstream.
        # Interface: generate(message_map: MessageMap) -> LabelDraft
        # Shares LLM-01 infrastructure with labeling-specific prompt configuration.
        section_claims = {}
        for claim in message_map.claims:
            section_claims.setdefault(claim.label_section, []).append(claim)

        section_map = {
            "Indications and Usage": ("indications_usage", self._draft_indications),
            "Clinical Studies": ("clinical_studies", self._draft_clinical_studies),
            "Warnings and Precautions": ("warnings_precautions", self._draft_warnings),
            "Adverse Reactions": ("adverse_reactions", self._draft_adverse_reactions),
        }

        sections = []
        for section_name, (section_id, draft_fn) in section_map.items():
            claims = section_claims.get(section_name, [])
            sections.append(draft_fn(section_id, section_name, claims, message_map))

        overall_conf = sum(s.confidence for s in sections) / max(len(sections), 1)

        return LabelDraft(
            draft_id=f"draft_{uuid.uuid4().hex[:8]}",
            map_id=message_map.map_id,
            program_name=message_map.program_name,
            indication=message_map.indication,
            document_type=message_map.document_type,
            regulatory_body=message_map.regulatory_body,
            simulation_mode=config.SIMULATION_MODE,
            sections=sections,
            overall_confidence=round(overall_conf, 2),
        )

    def _draft_indications(self, section_id, section_title, claims, map_) -> LabelSection:
        if config.SIMULATION_MODE == "high_quality":
            prose = (
                f"1 INDICATIONS AND USAGE\n\n"
                f"{map_.program_name.capitalize()} is indicated as an adjunct to a reduced-calorie "
                f"diet and increased physical activity for chronic weight management in adults with "
                f"an initial BMI of 30 kg/m² or greater (obesity), or 27 kg/m² or greater "
                f"(overweight) in the presence of at least one weight-related comorbidity "
                f"(e.g., hypertension, type 2 diabetes mellitus, or dyslipidemia).\n\n"
                f"Limitations of Use: The safety and efficacy of {map_.program_name.capitalize()} "
                f"in combination with other approved weight management drug products have not been "
                f"established. The safety and efficacy in patients with a history of pancreatitis "
                f"have not been established."
            )
            conf = 0.92
            rationale = "High quality: direct class-standard language from competitive precedent."
        else:
            prose = (
                f"1 INDICATIONS AND USAGE\n\n"
                f"{map_.program_name.capitalize()} is a treatment for weight management. "
                f"It should be used with diet and exercise. "
                f"[MISSING: specific BMI threshold language not confirmed from precedent]"
            )
            conf = 0.42
            rationale = "Low quality: generic language, missing mandatory BMI threshold specification."
        return LabelSection(
            section_id=section_id, section_title=section_title, prose=prose,
            source_claim_ids=[c.claim_id for c in claims],
            confidence=conf, confidence_rationale=rationale,
            has_gaps=any(c.is_gap for c in claims),
        )

    def _draft_clinical_studies(self, section_id, section_title, claims, map_) -> LabelSection:
        drug = map_.program_name.capitalize()
        if config.SIMULATION_MODE == "high_quality":
            phase = claims[0].supporting_value if claims and claims[0].supporting_value else "Phase 2"
            prose = (
                f"14 CLINICAL STUDIES\n\n"
                f"14.1 Overview\n\n"
                f"The efficacy of {drug} for chronic weight management was evaluated in ACCESS II, "
                f"a {phase}, randomized, double-blind, placebo-controlled, parallel-group study in "
                f"adults with obesity or overweight with weight-related comorbidities.\n\n"
                f"14.2 ACCESS II — Primary Efficacy Results\n\n"
                f"The primary efficacy endpoint was percent change from baseline in body weight at "
                f"Week 36. [Specific result: mean % change and 95% CI to be confirmed from final CSR data.]\n\n"
                f"Responder Analysis: The proportion of patients achieving at least 5% reduction in "
                f"body weight at Week 36 was [X]% in the {drug}-treated group compared with [Y]% in "
                f"the placebo group (p < 0.001). [Values to be confirmed from final CSR.]"
            )
            conf = 0.74
            rationale = "High quality: correct structure and mandatory elements; efficacy values pending Phase 3 data."
        else:
            prose = (
                f"14 CLINICAL STUDIES\n\n"
                f"{drug} was studied in a clinical trial. Results showed weight loss compared to "
                f"placebo. [MISSING: specific efficacy data, responder analysis, study design details]"
            )
            conf = 0.35
            rationale = "Low quality: missing mandatory responder analysis, no statistical detail, no study design."
        return LabelSection(
            section_id=section_id, section_title=section_title, prose=prose,
            source_claim_ids=[c.claim_id for c in claims],
            confidence=conf, confidence_rationale=rationale,
            has_gaps=any(c.is_gap for c in claims),
        )

    def _draft_warnings(self, section_id, section_title, claims, map_) -> LabelSection:
        drug = map_.program_name.capitalize()
        if config.SIMULATION_MODE == "high_quality":
            prose = (
                f"5 WARNINGS AND PRECAUTIONS\n\n"
                f"5.1 Risk of Thyroid C-Cell Tumors\n\n"
                f"{drug} causes dose-dependent and treatment-duration-dependent thyroid C-cell "
                f"tumors at clinically relevant exposures in both genders of rats and mice. It is "
                f"unknown whether {drug} causes thyroid C-cell tumors, including medullary thyroid "
                f"carcinoma (MTC), in humans, as the human relevance of {drug.lower()}-induced "
                f"rodent thyroid C-cell tumors has not been determined [see Contraindications (4) "
                f"and Nonclinical Toxicology (13.1)].\n\n"
                f"5.2 Pancreatitis\n\n"
                f"Acute pancreatitis, including fatal and non-fatal hemorrhagic or necrotizing "
                f"pancreatitis, has been observed in patients treated with GLP-1 receptor agonists. "
                f"After initiation of {drug}, observe patients carefully for signs and symptoms of "
                f"pancreatitis. If pancreatitis is suspected, promptly discontinue {drug} and "
                f"initiate appropriate management."
            )
            conf = 0.91
            rationale = "High quality: mandatory class-effect language reproduced accurately from competitive precedent."
        else:
            prose = (
                f"5 WARNINGS AND PRECAUTIONS\n\n"
                f"5.1 General\n\n"
                f"{drug} may cause thyroid tumors in animals. Monitor thyroid. "
                f"[MISSING: required boxed warning language, specific tumor type, human relevance "
                f"statement, cross-references to other sections]"
            )
            conf = 0.30
            rationale = "Low quality: missing mandatory boxed warning language. This would be a blocking FDA deficiency."
        return LabelSection(
            section_id=section_id, section_title=section_title, prose=prose,
            source_claim_ids=[c.claim_id for c in claims],
            confidence=conf, confidence_rationale=rationale,
            has_gaps=False,
        )

    def _draft_adverse_reactions(self, section_id, section_title, claims, map_) -> LabelSection:
        drug = map_.program_name.capitalize()
        if config.SIMULATION_MODE == "high_quality":
            prose = (
                f"6 ADVERSE REACTIONS\n\n"
                f"6.1 Clinical Trials Experience\n\n"
                f"Because clinical trials are conducted under widely varying conditions, adverse "
                f"reaction rates observed in the clinical trials of a drug cannot be directly "
                f"compared to rates in the clinical trials of another drug and may not reflect the "
                f"rates observed in practice.\n\n"
                f"The most common adverse reactions (incidence ≥5% and greater than placebo) "
                f"reported in ACCESS II were: nausea ([X]% vs [Y]% placebo), diarrhea ([X]% vs [Y]% "
                f"placebo), vomiting ([X]% vs [Y]% placebo), constipation ([X]% vs [Y]% placebo), "
                f"and abdominal pain ([X]% vs [Y]% placebo). [Specific incidence rates to be "
                f"confirmed from final ISS data.]"
            )
            conf = 0.78
            rationale = "High quality: correct structure and class-standard AE profile; rates pending ISS data."
        else:
            prose = (
                f"6 ADVERSE REACTIONS\n\n"
                f"Side effects of {drug} include nausea and other gastrointestinal symptoms. "
                f"[MISSING: specific incidence rates, placebo comparison, standard clinical trials "
                f"experience preamble]"
            )
            conf = 0.32
            rationale = "Low quality: missing required preamble, no placebo-controlled incidence data, non-regulatory language."
        return LabelSection(
            section_id=section_id, section_title=section_title, prose=prose,
            source_claim_ids=[c.claim_id for c in claims],
            confidence=conf, confidence_rationale=rationale,
            has_gaps=any(c.is_gap for c in claims),
        )

    def _generate_real(self, message_map: MessageMap) -> LabelDraft:
        # PROMOTION SLOT: LLM-15 full implementation
        raise NotImplementedError(
            "LLM-15 functional model not yet promoted. Set USE_STUB=true."
        )
