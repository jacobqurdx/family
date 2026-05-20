import pytest
from pathlib import Path

from agent.domain import (
    ActionType, RiskVectorType, SeverityTier, SignalSourceType,
)
from agent.mrp import load_sensitivity_context

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def test_severity_tier_values():
    assert SeverityTier.CRITICAL.value == "critical"
    assert SeverityTier.HIGH.value == "high"
    assert SeverityTier.ELEVATED.value == "elevated"
    assert SeverityTier.ROUTINE.value == "routine"


def test_action_type_enum():
    assert ActionType.ADD_TO_DIGEST.value == "add_to_digest"
    assert ActionType.SEND_ALERT.value == "send_alert"
    assert ActionType.TRIGGER_TARIFF_SWEEP.value == "trigger_tariff_sweep"


def test_sensitivity_context_fields():
    ctx = load_sensitivity_context(EXAMPLES_DIR / "sensitivity_report_wuxi.json")
    assert ctx.base_cost_per_kg_api == 5208.0
    assert ctx.currency == "USD"
    assert ctx.report_id == "sr-20260515-001"
    assert ctx.scenario_id == "api-001_route_a"


def test_signal_priority_weights_count():
    ctx = load_sensitivity_context(EXAMPLES_DIR / "sensitivity_report_wuxi.json")
    assert len(ctx.signal_priority_weights) == 10


def test_tariff_sweep_entries():
    ctx = load_sensitivity_context(EXAMPLES_DIR / "sensitivity_report_wuxi.json")
    assert len(ctx.tariff_sweep) == 4


def test_cdmo_removal_scenarios():
    ctx = load_sensitivity_context(EXAMPLES_DIR / "sensitivity_report_wuxi.json")
    assert len(ctx.cdmo_removal_scenarios) == 1


def test_risk_vector_type_enum():
    assert RiskVectorType.TARIFF_ESCALATION.value == "tariff_escalation"
    assert RiskVectorType.CDMO_REMOVAL.value == "cdmo_removal"
    assert RiskVectorType.UNKNOWN.value == "unknown"


def test_signal_source_type_enum():
    assert SignalSourceType.FILE.value == "file"
    assert SignalSourceType.WEB_SEARCH.value == "web_search"
