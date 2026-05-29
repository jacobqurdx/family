import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.schema import SchemaRegistry
from core.twin import DigitalTwin
from generation.generator import ProseGenerator
from llm.stub import LLMStub


@pytest.fixture
def registry():
    return SchemaRegistry()


@pytest.fixture
def twin():
    return DigitalTwin.load("synth_phase2_trial")


@pytest.fixture
def generator():
    return ProseGenerator(use_real_llm=False)


def test_stub_generates_all_protocol_sections(generator, registry, twin):
    schema = registry.get("protocol")
    for section in schema.sections:
        source_data = twin.get_section_data(section.source_elements)
        result = generator.generate(section.id, section.title, source_data)
        assert result.prose
        assert len(result.prose) > 20
        assert result.section_id == section.id


def test_stub_substitutes_source_values():
    stub = LLMStub()
    source_data = {
        "drug_name": "STR-4021",
        "indication": "type 2 diabetes mellitus",
        "study_phase": "Phase 2",
        "design_type": "randomized, double-blind, placebo-controlled, parallel-group",
        "study_duration_weeks": "28"
    }
    result = stub.generate_section(
        "study_design_narrative",
        "Study Design",
        source_data,
        ""
    )
    assert "STR-4021" in result.prose
    assert "type 2 diabetes mellitus" in result.prose


def test_confidence_lower_when_unresolved_placeholders():
    stub = LLMStub()
    # Provide only partial data — some placeholders will remain
    result = stub.generate_section(
        "primary_endpoint_narrative",
        "Primary Endpoint",
        {"primary_endpoint": "change from baseline in HbA1c"},
        ""
    )
    # Should still have unresolved brackets → lower confidence
    assert result.confidence < 0.8


def test_confidence_high_when_all_substituted():
    stub = LLMStub()
    # A known section with all source keys provided — no unresolved brackets
    result = stub.generate_section(
        "study_design_narrative",
        "Study Design",
        {
            "drug_name": "STR-4021",
            "indication": "type 2 diabetes mellitus",
            "study_phase": "Phase 2",
            "design_type": "randomized, double-blind, placebo-controlled, parallel-group",
            "study_duration_weeks": "28",
        },
        ""
    )
    assert result.confidence >= 0.8


def test_generated_section_metadata(generator, twin, registry):
    schema = registry.get("protocol")
    section = schema.sections[0]
    source_data = twin.get_section_data(section.source_elements)
    result = generator.generate(section.id, section.title, source_data)

    assert result.model_used == "stub"
    assert result.prompt_version == "stub_v1"
    assert 0.0 <= result.confidence <= 1.0
    assert result.confidence_rationale


def test_unknown_section_gets_fallback_prose(generator):
    result = generator.generate("custom_unknown_section", "Custom Section", {"data": "value"})
    assert "STUB" in result.prose
    assert "custom_unknown_section" in result.prose.lower() or "Custom Section" in result.prose
