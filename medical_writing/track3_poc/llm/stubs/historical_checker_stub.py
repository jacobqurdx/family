# PROMOTION SLOT: HistoricalChecker
# Replace with functional HistoricalChecker (embedding similarity + LLM reasoning)
# from LLM workstream at Beta maturity (requires labeled CRL dataset).
# Interface: check(spec: ContentSpec, framework_twin: RegulatoryFrameworkTwin) -> list[QCFinding]
from review.finding_models import QCFinding
import config


class HistoricalCheckerStub:
    """
    Checks content specification claims against known agency concerns and prior
    company positions. Stub uses hardcoded synthetic findings.
    """

    def check(self, spec, framework_twin) -> list:
        if config.SIMULATION_MODE == "low_quality":
            return [QCFinding(
                finding_id="hist_001",
                section_id="cardiovascular_safety",
                pass_number=2,
                severity="blocking",
                category="prior_crl_concern",
                description=(
                    "FDA has previously raised concerns about cardiovascular safety monitoring "
                    "adequacy for GLP-1 agonists in obesity. The cardiovascular safety plan "
                    "section does not reference the specific MACE adjudication committee "
                    "requirements raised in the 2022 agency correspondence."
                ),
                offending_text="comprehensive cardiovascular safety monitoring plan",
                role_relevance=["regulatory_affairs"],
                suggested_resolution="Explicitly reference MACE adjudication committee and cite prior agency correspondence.",
                prior_position_id="agency_concern_glp1_cv_2022",
            )]
        return []
