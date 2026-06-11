"""
CITwinManager: loads, queries, and updates the competitive intelligence twin.

The CI twin is pre-populated for the POC from publicly available approved labels:
- Semaglutide (Wegovy)   — FDA approved 2021 for obesity
- Tirzepatide (Zepbound) — FDA approved 2023 for obesity
- Liraglutide (Saxenda)  — FDA approved 2014 for obesity

Source: DailyMed (https://dailymed.nlm.nih.gov/) and the FDA label repository.
All content is structured extraction of real, publicly available prescribing
information. Automated extraction is LLM workstream item LLM-13.
"""
import json
from pathlib import Path
from typing import Optional

from labeling.labeling_models import CompetitiveIntelligenceTwin, ApprovedClaim
import config


class CITwinManager:
    def __init__(self, ci_dir: Optional[str] = None):
        self._dir = Path(ci_dir or config.CI_TWINS_DIR)

    def list_ids(self) -> list:
        return sorted(f.stem for f in self._dir.glob("*.json"))

    def load(self, ci_twin_id: str) -> CompetitiveIntelligenceTwin:
        path = self._dir / f"{ci_twin_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"CI twin not found: {ci_twin_id}")
        return CompetitiveIntelligenceTwin(**json.loads(path.read_text()))

    @staticmethod
    def rebuild_index(ci_twin: CompetitiveIntelligenceTwin) -> CompetitiveIntelligenceTwin:
        """Recompute claims_by_section from the current approved_claims list."""
        index = {}
        for c in ci_twin.approved_claims:
            index.setdefault(c.label_section, []).append(c.claim_id)
        ci_twin.claims_by_section = index
        return ci_twin

    def save(self, ci_twin: CompetitiveIntelligenceTwin, bump_version: bool = True) -> None:
        """Persist the CI twin back to disk. The CI twin is shared across all
        programs in the indication class — saving is a deliberate library edit."""
        import datetime
        self.rebuild_index(ci_twin)
        if bump_version:
            try:
                major = int(float(ci_twin.version))
                ci_twin.version = f"{major + 1}.0"
            except (ValueError, TypeError):
                ci_twin.version = f"{ci_twin.version}+1"
        ci_twin.last_updated = datetime.datetime.utcnow()
        path = self._dir / f"{ci_twin.ci_twin_id}.json"
        path.write_text(ci_twin.model_dump_json(indent=2))

    def get_claims_for_section(self, ci_twin: CompetitiveIntelligenceTwin,
                               label_section: str) -> list:
        """All approved claims for a given label section across all competitors."""
        return [c for c in ci_twin.approved_claims
                if c.label_section.lower() == label_section.lower()]

    def get_achievability_ceiling(self, ci_twin: CompetitiveIntelligenceTwin,
                                  label_section: str,
                                  our_evidence_value: float = None) -> str:
        """Assess achievability for a proposed claim based on competitive precedent."""
        section_claims = self.get_claims_for_section(ci_twin, label_section)
        if not section_claims:
            return "low"
        if our_evidence_value and any(c.quantitative_threshold for c in section_claims):
            return "high"
        return "medium"

    def generate_precedent_summary(self, ci_twin: CompetitiveIntelligenceTwin,
                                   claim_ids: list) -> str:
        """Plain-English precedent summary from a list of approved claim IDs."""
        claims = [c for c in ci_twin.approved_claims if c.claim_id in claim_ids]
        if not claims:
            return "No competitive precedent found for this claim type."
        drug_names = list({c.drug_name for c in claims})
        sections = list({c.label_section for c in claims})
        return (
            f"{', '.join(drug_names)} {'have' if len(drug_names) > 1 else 'has'} "
            f"approved label language in {', '.join(sections)} for comparable claims "
            f"in obesity. See CI twin claims {', '.join(claim_ids)} for full detail."
        )
