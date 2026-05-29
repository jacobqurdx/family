"""
LLMClient: real Anthropic API calls.
Used when USE_STUB=false. Implements the same interface as LLMStub.
"""
import anthropic
from core.models import GeneratedSection, QCResult, QCFinding
from llm.prompts import get_generation_prompt, get_qc_prompt, PROMPT_VERSION
import config


class LLMClient:
    def __init__(self):
        self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    def generate_section(self, section_id: str, section_title: str,
                         source_data: dict, prompt: str) -> GeneratedSection:
        system_prompt = get_generation_prompt(section_id)
        user_message = (
            f"Generate regulatory prose for section: {section_title}\n\n"
            f"Source data from digital twin:\n"
            + "\n".join(f"  {k}: {v}" for k, v in source_data.items() if v is not None)
            + f"\n\nRequirements:\n{prompt}"
        )
        response = self._client.messages.create(
            model=config.MODEL,
            max_tokens=config.MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        prose = response.content[0].text
        confidence, rationale = self._assess_confidence(prose, source_data)

        return GeneratedSection(
            section_id=section_id,
            section_title=section_title,
            prose=prose,
            source_elements=source_data,
            model_used=config.MODEL,
            prompt_version=PROMPT_VERSION,
            confidence=confidence,
            confidence_rationale=rationale
        )

    def _assess_confidence(self, prose: str, source_data: dict) -> tuple[float, str]:
        response = self._client.messages.create(
            model=config.MODEL,
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": (
                    f"Rate your confidence in this regulatory prose on a scale of 0.0 to 1.0. "
                    f"Consider: citation accuracy, regulatory appropriateness, completeness. "
                    f"Respond with ONLY: <score>0.XX</score><rationale>one sentence</rationale>\n\n"
                    f"Prose:\n{prose}"
                )
            }]
        )
        raw = response.content[0].text
        try:
            import re
            score = float(re.search(r"<score>([\d.]+)</score>", raw).group(1))
            rationale = re.search(r"<rationale>(.*?)</rationale>", raw, re.DOTALL).group(1).strip()
        except Exception:
            score = 0.7
            rationale = "Could not parse confidence assessment."
        return score, rationale

    def run_qc(self, section: GeneratedSection, source_data: dict) -> QCResult:
        system_prompt = get_qc_prompt()
        user_message = (
            f"QC check for section: {section.section_title}\n\n"
            f"Source data (ground truth):\n"
            + "\n".join(f"  {k}: {v}" for k, v in source_data.items() if v is not None)
            + f"\n\nGenerated prose:\n{section.prose}\n\n"
            f"Check for: unsupported claims, citation errors, characterization drift, "
            f"internal inconsistencies. Return findings as JSON array with fields: "
            f"severity, category, description, offending_text, source_element."
        )
        response = self._client.messages.create(
            model=config.MODEL,
            max_tokens=config.MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        raw = response.content[0].text
        findings = self._parse_qc_findings(raw, section.section_id)
        blocking = [f for f in findings if f.severity == "blocking"]
        major = [f for f in findings if f.severity == "major"]

        passed = len(blocking) == 0
        if blocking:
            recommendation = "escalate"
        elif major:
            recommendation = "revise"
        else:
            recommendation = "approve"

        return QCResult(
            section_id=section.section_id,
            passed=passed,
            findings=findings,
            overall_confidence=section.confidence,
            recommendation=recommendation
        )

    def _parse_qc_findings(self, raw: str, section_id: str) -> list[QCFinding]:
        import json, re
        findings = []
        try:
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if match:
                items = json.loads(match.group())
                for i, item in enumerate(items):
                    findings.append(QCFinding(
                        finding_id=f"qc_{i:03d}",
                        section_id=section_id,
                        severity=item.get("severity", "minor"),
                        category=item.get("category", "other"),
                        description=item.get("description", ""),
                        offending_text=item.get("offending_text"),
                        source_element=item.get("source_element")
                    ))
        except Exception:
            pass
        return findings
