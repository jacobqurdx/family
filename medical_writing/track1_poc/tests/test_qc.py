import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm.stub import LLMStub
from generation.qc_agent import QCAgent
from core.models import GeneratedSection


def make_section(section_id: str, prose: str) -> GeneratedSection:
    return GeneratedSection(
        section_id=section_id,
        section_title="Test Section",
        prose=prose,
        source_elements={"drug_name": "STR-4021"},
        model_used="stub",
        prompt_version="stub_v1",
        confidence=0.85,
        confidence_rationale="Test"
    )


@pytest.fixture
def stub():
    return LLMStub()


@pytest.fixture
def qc_agent():
    return QCAgent(use_real_llm=False)


def test_stub_qc_pass_when_no_placeholders(stub):
    section = make_section("primary_endpoint_narrative",
                           "The primary efficacy endpoint is change from baseline in HbA1c at Week 24.")
    result = stub.run_qc(section, {"primary_endpoint": "HbA1c"})
    assert result.passed is True
    assert result.recommendation == "approve"
    assert result.findings == []


def test_stub_qc_warning_when_placeholders_remain(stub):
    section = make_section("study_design_narrative",
                           "This study evaluates [DRUG_NAME] in patients with [INDICATION].")
    result = stub.run_qc(section, {})
    assert result.recommendation == "revise"
    assert len(result.findings) > 0


def test_qc_finding_has_correct_section_id(stub):
    section = make_section("stat_analysis", "Analysis using [METHOD] approach.")
    result = stub.run_qc(section, {})
    for finding in result.findings:
        assert finding.section_id == "stat_analysis"


def test_qc_agent_delegates_to_stub(qc_agent):
    section = make_section("primary_endpoint_narrative",
                           "The primary endpoint is HbA1c at Week 24.")
    result = qc_agent.check(section, {"primary_endpoint": "HbA1c"})
    assert result.section_id == "primary_endpoint_narrative"
    assert result.recommendation in ("approve", "revise", "escalate")


def test_qc_result_fields_complete(stub):
    section = make_section("test_section", "Clean prose without brackets.")
    result = stub.run_qc(section, {})
    assert result.section_id == "test_section"
    assert isinstance(result.passed, bool)
    assert isinstance(result.findings, list)
    assert 0.0 <= result.overall_confidence <= 1.0
    assert result.recommendation in ("approve", "revise", "escalate")


def test_qc_finding_fields_complete(stub):
    section = make_section("study_design_narrative",
                           "Evaluating [DRUG_NAME] in [INDICATION].")
    result = stub.run_qc(section, {})
    assert len(result.findings) > 0
    f = result.findings[0]
    assert f.finding_id
    assert f.severity in ("blocking", "major", "minor")
    assert f.category
    assert f.description
