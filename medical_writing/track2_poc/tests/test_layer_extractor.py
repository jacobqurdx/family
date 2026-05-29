"""
Tests for usdm/extractor.py (stub mode — no API key needed)
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from usdm.extractor import LayerExtractor, STUB_EXTRACTIONS
from usdm.graph_walk import ALL_LAYERS, get_layer_nodes


def get_stub_extractor() -> LayerExtractor:
    return LayerExtractor(use_stub=True)


def test_stub_mode_enabled():
    extractor = get_stub_extractor()
    assert extractor._use_stub is True


def test_stub_extraction_layer_0():
    extractor = get_stub_extractor()
    result = extractor.extract_layer(0, None, {})
    assert result.layer_index == 0
    assert result.model_used == "stub"
    assert len(result.extracted_nodes) == 12  # Layer 0 has 12 nodes


def test_stub_extraction_all_layers():
    extractor = get_stub_extractor()
    for layer_idx in range(9):
        result = extractor.extract_layer(layer_idx, None, {})
        expected_count = len(get_layer_nodes(layer_idx))
        assert len(result.extracted_nodes) == expected_count, \
            f"Layer {layer_idx}: expected {expected_count} nodes, got {len(result.extracted_nodes)}"


def test_stub_extraction_layer_0_drug_name():
    extractor = get_stub_extractor()
    result = extractor.extract_layer(0, None, {})
    nodes = get_layer_nodes(0)
    node_ids = [n.id for n in nodes]
    drug_idx = node_ids.index("drug_name")
    drug_item = result.extracted_nodes[drug_idx]
    assert drug_item.value == "STR-4021"


def test_stub_extraction_layer_0_indication():
    extractor = get_stub_extractor()
    result = extractor.extract_layer(0, None, {})
    nodes = get_layer_nodes(0)
    node_ids = [n.id for n in nodes]
    ind_idx = node_ids.index("indication")
    ind_item = result.extracted_nodes[ind_idx]
    assert "type 2 diabetes" in ind_item.value.lower()


def test_stub_extraction_layer_3_eligibility_criteria():
    """Layer 3 uses USDM EligibilityCriterion objects (replaces flat inclusion/exclusion lists)."""
    extractor = get_stub_extractor()
    result = extractor.extract_layer(3, None, {})
    nodes = get_layer_nodes(3)
    node_ids = [n.id for n in nodes]
    ec_idx = node_ids.index("eligibility_criteria")
    ec_item = result.extracted_nodes[ec_idx]
    assert isinstance(ec_item.value, list)
    # Should have at least 5 inclusion + 5 exclusion = 10 criteria
    assert len(ec_item.value) >= 10
    # Each item should be a dict with USDM EligibilityCriterion fields
    first = ec_item.value[0]
    assert isinstance(first, dict)
    assert "category" in first
    assert first["category"] in ("INCLUSION", "EXCLUSION")
    assert "text" in first
    assert "identifier" in first


def test_stub_extraction_confidence():
    extractor = get_stub_extractor()
    result = extractor.extract_layer(0, None, {})
    for item in result.extracted_nodes:
        assert 0.0 <= item.confidence <= 1.0


def test_prompt_context_with_confirmed_values():
    extractor = get_stub_extractor()
    confirmed = {
        "indication": "type 2 diabetes mellitus with inadequate glycemic control on metformin monotherapy",
        "study_phase": "Phase 2",
    }
    context_str = extractor.build_prompt_context(1, confirmed)
    assert "indication" in context_str
    assert "study_phase" in context_str
    assert "Phase 2" in context_str


def test_prompt_context_empty_confirmed():
    extractor = get_stub_extractor()
    context_str = extractor.build_prompt_context(0, {})
    # Layer 0 has no parents, so all constraints should say no parent constraints
    assert "No confirmed parent constraints" in context_str


def test_stub_total_node_count():
    """Total across all layers should be 46 (USDM-faithful refactor: consolidated lists replace flat nodes)."""
    total = sum(len(layer) for layer in ALL_LAYERS)
    assert total == 46


def test_stub_layer_enrollment_target():
    extractor = get_stub_extractor()
    result = extractor.extract_layer(1, None, {})
    nodes = get_layer_nodes(1)
    node_ids = [n.id for n in nodes]
    et_idx = node_ids.index("enrollment_target")
    et_item = result.extracted_nodes[et_idx]
    assert et_item.value == 240
