"""
LLMStub: returns deterministic canned prose outputs for every section.
Used when USE_STUB=true (default). No API calls.
"""
from core.models import GeneratedSection, QCResult, QCFinding


STUB_PROSE = {
    "study_design_narrative": (
        "This is a Phase 2, randomized, double-blind, placebo-controlled study "
        "evaluating [DRUG_NAME] in adult patients with [INDICATION]. The study employs "
        "a parallel-group design with a [STUDY_DURATION_WEEKS]-week treatment period followed "
        "by a safety follow-up."
    ),
    "primary_endpoint_narrative": (
        "The primary efficacy endpoint is change from baseline in [PRIMARY_ENDPOINT] "
        "at [PRIMARY_ENDPOINT_TIMEPOINT], assessed using a validated instrument. This endpoint "
        "was selected based on established regulatory precedent in [INDICATION] and its clinical "
        "relevance to the patient population."
    ),
    "inclusion_exclusion_narrative": (
        "Eligible participants are adults aged [POPULATION_AGE_MIN] to [POPULATION_AGE_MAX] years "
        "with a confirmed diagnosis of [INDICATION] meeting the following criteria: "
        "[INCLUSION_CRITERIA]. Patients are excluded if they meet any of the following "
        "criteria: [EXCLUSION_CRITERIA]."
    ),
    "statistical_analysis_narrative": (
        "The primary analysis will be conducted on the full analysis set using a "
        "[PRIMARY_ANALYSIS_TYPE] model. The primary endpoint [PRIMARY_ENDPOINT] will be "
        "analyzed using [PRIMARY_ANALYSIS_TYPE] with treatment group as the primary factor "
        "and relevant covariates."
    ),
    "safety_monitoring_narrative": (
        "Safety will be monitored continuously throughout the study. An independent "
        "Data Safety Monitoring Board (DSMB) will review unblinded safety data at "
        "pre-specified intervals."
    ),
}

STUB_QC_RESULTS = {
    "pass": QCResult(
        section_id="",
        passed=True,
        findings=[],
        overall_confidence=0.85,
        recommendation="approve"
    ),
    "warning": QCResult(
        section_id="",
        passed=True,
        findings=[
            QCFinding(
                finding_id="qc_001",
                section_id="",
                severity="minor",
                category="characterization_drift",
                description="Stub warning: placeholder values detected in generated prose. "
                            "Verify that all [BRACKETED] values were replaced with actual trial data.",
                offending_text="[DRUG_NAME]",
                source_element="drug_name"
            )
        ],
        overall_confidence=0.65,
        recommendation="revise"
    )
}


class LLMStub:
    def generate_section(self, section_id: str, section_title: str,
                         source_data: dict, prompt: str) -> GeneratedSection:
        base_prose = STUB_PROSE.get(
            section_id,
            f"[STUB] Generated prose for section '{section_title}'. "
            f"Source data contained {len(source_data)} elements. "
            f"Replace this stub with real LLM output."
        )
        prose = base_prose
        for key, val in source_data.items():
            if val is not None:
                prose = prose.replace(f"[{key.upper()}]", str(val))

        has_unresolved = "[" in prose and "]" in prose
        confidence = 0.65 if has_unresolved else 0.85

        return GeneratedSection(
            section_id=section_id,
            section_title=section_title,
            prose=prose,
            source_elements=source_data,
            model_used="stub",
            prompt_version="stub_v1",
            confidence=confidence,
            confidence_rationale=(
                "Stub: confidence reduced because unresolved placeholders remain."
                if has_unresolved else
                "Stub: all source elements substituted."
            )
        )

    def run_qc(self, section: GeneratedSection, source_data: dict) -> QCResult:
        has_unresolved = "[" in section.prose and "]" in section.prose
        result = STUB_QC_RESULTS["warning" if has_unresolved else "pass"].model_copy()
        result.section_id = section.section_id
        for finding in result.findings:
            finding.section_id = section.section_id
        return result
