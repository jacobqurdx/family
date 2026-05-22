from __future__ import annotations
"""Tests for the multi-scenario comparator (v1.2)."""
from pathlib import Path
import pytest

from agent.domain import (
    Signal, SignalSourceType,
    RelevanceResult, NoveltyResult, SeverityResult, ImpactResult,
    AssessedSignal, SeverityTier, RiskVectorType, ActionType,
    RiskProfile, RiskProfileParameter, RiskProfileScenario, ScenarioImpact,
)
from agent.rule_engine import load_risk_profile_yaml, compare_across_scenarios

PROFILE_PATH = Path(__file__).parent.parent / "examples" / "risk_profile.yaml"


@pytest.fixture
def profile():
    return load_risk_profile_yaml(PROFILE_PATH)


def _make_assessed(relevant_parameters: list[str]) -> AssessedSignal:
    import hashlib
    content = "test signal content"
    signal = Signal(
        id="test_signal",
        source_type=SignalSourceType.FILE,
        source_name="Test",
        source_url=None,
        collected_at="2026-05-15T10:00:00Z",
        raw_content=content,
        raw_content_hash=hashlib.sha256(content.encode()).hexdigest(),
    )
    return AssessedSignal(
        signal=signal,
        relevance=RelevanceResult(
            is_relevant=True,
            relevant_parameters=relevant_parameters,
            relevance_reasoning="test",
            prompt_version="1.0.0",
        ),
        novelty=NoveltyResult(
            is_novel=True,
            novelty_reasoning="test",
            updated_parameter_states=[],
            prompt_version="1.0.0",
        ),
        severity=SeverityResult(
            severity=SeverityTier.HIGH,
            severity_reasoning="test",
            risk_vector_type=RiskVectorType.TARIFF_ESCALATION,
            affected_geography="CN",
            affected_cdmo_node_name=None,
            prompt_version="1.0.0",
        ),
        impact=ImpactResult(
            estimated_cost_impact_per_kg=115.84,
            estimated_cost_impact_reasoning="test",
            estimated_timeline_impact_weeks=None,
            estimated_timeline_reasoning="",
            confidence="high",
            caveats=[],
            prompt_version="1.0.0",
        ),
        recommended_actions=[ActionType.SEND_ALERT],
    )


# ─── Single scenario match ────────────────────────────────────────────────────

def test_single_scenario_match(profile):
    """
    WuXi STA CDMO Risk only applies to our_current.
    Assessed signal with that parameter → one ScenarioImpact returned.
    """
    assessed = _make_assessed(relevant_parameters=["WuXi STA CDMO Risk"])
    results = compare_across_scenarios(assessed, profile)
    assert len(results) == 1
    assert results[0].scenario_id == "our_current"


def test_single_scenario_primary_flag(profile):
    assessed = _make_assessed(relevant_parameters=["WuXi STA CDMO Risk"])
    results = compare_across_scenarios(assessed, profile)
    assert results[0].is_primary is True


# ─── Multi-scenario match ─────────────────────────────────────────────────────

def test_multi_scenario_match(profile):
    """
    CN Section 301 Tariff applies to [our_current, competitor_x].
    Assessed signal → two ScenarioImpacts returned.
    """
    assessed = _make_assessed(
        relevant_parameters=["CN Section 301 Tariff — API Starting Materials"]
    )
    results = compare_across_scenarios(assessed, profile)
    scenario_ids = {r.scenario_id for r in results}
    assert "our_current" in scenario_ids
    assert "competitor_x" in scenario_ids
    assert len(results) == 2


def test_multi_scenario_primary_flag_only_on_primary(profile):
    """Only our_current is primary."""
    assessed = _make_assessed(
        relevant_parameters=["CN Section 301 Tariff — API Starting Materials"]
    )
    results = compare_across_scenarios(assessed, profile)
    primary_results = [r for r in results if r.is_primary]
    non_primary = [r for r in results if not r.is_primary]
    assert len(primary_results) == 1
    assert primary_results[0].scenario_id == "our_current"
    assert len(non_primary) == 1
    assert non_primary[0].scenario_id == "competitor_x"


# ─── No MRP enrichment ────────────────────────────────────────────────────────

def test_no_mrp_enrichment_gives_estimated_data_source(profile):
    """No context passed → cost_delta_per_kg=None, data_source='estimated'."""
    assessed = _make_assessed(relevant_parameters=["WuXi STA CDMO Risk"])
    results = compare_across_scenarios(assessed, profile, context=None)
    assert results[0].cost_delta_per_kg is None
    assert results[0].data_source == "estimated"


def test_no_mrp_enrichment_scenario_has_no_mrp_id(profile):
    """
    competitor_x has mrp_scenario_id=None → no MRP enrichment even if
    context is available.
    """
    from agent.mrp import load_sensitivity_context
    ctx_path = Path(__file__).parent.parent / "examples" / "sensitivity_report_wuxi.json"
    context = load_sensitivity_context(ctx_path)

    assessed = _make_assessed(
        relevant_parameters=["CN Section 301 Tariff — API Starting Materials"]
    )
    results = compare_across_scenarios(assessed, profile, context=context)

    our_current = next(r for r in results if r.scenario_id == "our_current")
    competitor_x = next(r for r in results if r.scenario_id == "competitor_x")

    # our_current has mrp_scenario_id → can use MRP data
    assert our_current.cost_delta_per_kg == pytest.approx(115.84)
    assert our_current.data_source == "mrp"

    # competitor_x has no mrp_scenario_id → estimated
    assert competitor_x.cost_delta_per_kg is None
    assert competitor_x.data_source == "estimated"


# ─── Qualitative impact from risk_tier ───────────────────────────────────────

def test_qualitative_impact_from_risk_tier(profile):
    """
    When no MRP data: qualitative_impact = risk_tier of the matched parameter.
    """
    assessed = _make_assessed(relevant_parameters=["WuXi STA CDMO Risk"])
    results = compare_across_scenarios(assessed, profile, context=None)
    # WuXi STA CDMO Risk has risk_tier=HIGH
    assert results[0].qualitative_impact == "HIGH"


def test_no_match_returns_empty_list(profile):
    """Relevant parameters not in any profile parameter → empty list."""
    assessed = _make_assessed(relevant_parameters=["Unknown Parameter XYZ"])
    results = compare_across_scenarios(assessed, profile)
    assert results == []
