from __future__ import annotations
"""
Tests for the rule-based assessment engine (v1.2/v1.3).
All tests run without any LLM calls or API key.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.domain import (
    InternalSignal, InternalThresholds, SeverityTier, SignalState,
)
from agent.rule_engine import (
    load_risk_profile_yaml,
    assess_internal_signal,
    _compute_severity,
    _check_novelty,
    _internal_to_signal,
)

# ─── Fixtures ─────────────────────────────────────────────────────────────────

PROFILE_PATH = Path(__file__).parent.parent / "examples" / "risk_profile.yaml"


@pytest.fixture
def profile():
    return load_risk_profile_yaml(PROFILE_PATH)


def _make_internal(
    param_id: str = "step_3_yield",
    actual: float = 52.2,
    planned: float = 74.0,
    signal_type: str = "step_yield",
    unit: str = "%",
    signal_id: str | None = None,
) -> InternalSignal:
    return InternalSignal(
        id=signal_id or f"test_{param_id}",
        signal_type=signal_type,
        source_system="mes",
        parameter_id=param_id,
        scenario_id="our_current",
        actual_value=actual,
        planned_value=planned,
        unit=unit,
        measurement_timestamp="2026-05-15T06:00:00Z",
        context={},
    )


def _make_state(baseline: float, param_name: str = "Amide Coupling Step Yield") -> SignalState:
    return SignalState(
        parameter_name=param_name,
        last_updated_at="2026-05-01T00:00:00Z",
        last_signal_source=None,
        current_state_summary=f"Baseline: {baseline}",
        baseline_value=baseline,
        baseline_value_unit="%",
        last_known_change_direction="stable",
        risk_level="normal",
        source_url=None,
    )


# ─── Threshold computation — ratio type ───────────────────────────────────────

def test_ratio_routine():
    t = InternalThresholds(
        planned_value=74.0, unit="%",
        elevated_threshold=0.85, high_threshold=0.75, critical_threshold=0.65,
        threshold_type="ratio",
    )
    tier, reasoning = _compute_severity(73.1, t)
    assert tier == SeverityTier.ROUTINE
    assert "98.8" in reasoning or "98" in reasoning  # 73.1/74.0 = 98.8%


def test_ratio_elevated():
    t = InternalThresholds(
        planned_value=74.0, unit="%",
        elevated_threshold=0.85, high_threshold=0.75, critical_threshold=0.65,
        threshold_type="ratio",
    )
    tier, reasoning = _compute_severity(61.0, t)
    assert tier == SeverityTier.ELEVATED
    assert "82" in reasoning  # 61.0/74.0 = 82.4%


def test_ratio_high():
    t = InternalThresholds(
        planned_value=74.0, unit="%",
        elevated_threshold=0.85, high_threshold=0.75, critical_threshold=0.65,
        threshold_type="ratio",
    )
    tier, reasoning = _compute_severity(52.2, t)
    assert tier == SeverityTier.HIGH
    assert "70.5" in reasoning  # 52.2/74.0 = 70.5%
    assert "planned 74.0" in reasoning


def test_ratio_critical():
    t = InternalThresholds(
        planned_value=74.0, unit="%",
        elevated_threshold=0.85, high_threshold=0.75, critical_threshold=0.65,
        threshold_type="ratio",
    )
    tier, reasoning = _compute_severity(46.0, t)
    assert tier == SeverityTier.CRITICAL
    assert "62" in reasoning  # 46.0/74.0 = 62.2%


def test_ratio_zero_planned_returns_routine():
    t = InternalThresholds(
        planned_value=0.0, unit="%",
        elevated_threshold=0.85, high_threshold=0.75, critical_threshold=0.65,
        threshold_type="ratio",
    )
    tier, _ = _compute_severity(52.2, t)
    assert tier == SeverityTier.ROUTINE


# ─── Threshold computation — absolute type ────────────────────────────────────

def test_absolute_routine():
    t = InternalThresholds(
        planned_value=0.0, unit="%",
        elevated_threshold=2.0, high_threshold=5.0, critical_threshold=10.0,
        threshold_type="absolute",
    )
    tier, _ = _compute_severity(1.5, t)
    assert tier == SeverityTier.ROUTINE


def test_absolute_elevated():
    t = InternalThresholds(
        planned_value=0.0, unit="%",
        elevated_threshold=2.0, high_threshold=5.0, critical_threshold=10.0,
        threshold_type="absolute",
    )
    tier, _ = _compute_severity(3.5, t)
    assert tier == SeverityTier.ELEVATED


def test_absolute_high():
    t = InternalThresholds(
        planned_value=0.0, unit="%",
        elevated_threshold=2.0, high_threshold=5.0, critical_threshold=10.0,
        threshold_type="absolute",
    )
    tier, _ = _compute_severity(7.0, t)
    assert tier == SeverityTier.HIGH


def test_absolute_critical():
    t = InternalThresholds(
        planned_value=0.0, unit="%",
        elevated_threshold=2.0, high_threshold=5.0, critical_threshold=10.0,
        threshold_type="absolute",
    )
    tier, _ = _compute_severity(12.0, t)
    assert tier == SeverityTier.CRITICAL


# ─── SDD capacity_constraint signals (v1.3) ───────────────────────────────────

def test_sdd_global_fraction_routine(profile):
    sig = _make_internal(
        param_id="sdd_global_fraction",
        actual=4.1, planned=4.1,
        signal_type="sdd_global_fraction",
        unit="% of global capacity",
    )
    result = assess_internal_signal(sig, profile, {})
    # 4.1 < elevated_threshold(20) → ROUTINE, but not novel (0% change)
    assert result.relevance.is_relevant is True
    assert result.novelty is not None
    assert result.novelty.is_novel is False


def test_sdd_global_fraction_high(profile):
    sig = _make_internal(
        param_id="sdd_global_fraction",
        actual=38.0, planned=4.1,
        signal_type="sdd_global_fraction",
        unit="% of global capacity",
    )
    result = assess_internal_signal(sig, profile, {})
    assert result.relevance.is_relevant is True
    assert result.novelty is not None
    assert result.novelty.is_novel is True
    assert result.severity is not None
    assert result.severity.severity == SeverityTier.HIGH
    assert "38.0" in result.severity.severity_reasoning
    assert "35.0" in result.severity.severity_reasoning  # HIGH threshold


def test_sdd_global_fraction_critical(profile):
    t = InternalThresholds(
        planned_value=0.0, unit="% of global capacity",
        elevated_threshold=20.0, high_threshold=35.0, critical_threshold=50.0,
        threshold_type="absolute",
    )
    tier, reasoning = _compute_severity(52.0, t)
    assert tier == SeverityTier.CRITICAL
    assert "52.0" in reasoning


# ─── SDD novelty ──────────────────────────────────────────────────────────────

def test_sdd_fraction_not_novel_when_baseline_unchanged(profile):
    """4.1% actual == 4.1% planned → 0% change → NOT novel."""
    sig = _make_internal(
        param_id="sdd_global_fraction",
        actual=4.1, planned=4.1,
        signal_type="sdd_global_fraction",
    )
    result = assess_internal_signal(sig, profile, {})
    assert result.novelty.is_novel is False


def test_sdd_fraction_novel_when_increases_materially(profile):
    """38% vs 4.1% planned → 827% change → novel."""
    sig = _make_internal(
        param_id="sdd_global_fraction",
        actual=38.0, planned=4.1,
        signal_type="sdd_global_fraction",
    )
    result = assess_internal_signal(sig, profile, {})
    assert result.novelty.is_novel is True


# ─── Novelty — state-based checks ────────────────────────────────────────────

def test_novelty_novel_no_prior_state(profile):
    """No prior state + significant deviation from planned → novel."""
    sig = _make_internal(actual=52.2, planned=74.0)
    is_novel, _, _ = _check_novelty(
        sig, profile.get_parameter("step_3_yield"), {}
    )
    assert is_novel is True


def test_novelty_novel_large_change_from_prior(profile):
    """Prior baseline=74.0, actual=52.2 → 29.5% change > 5% → novel."""
    sig = _make_internal(actual=52.2, planned=74.0)
    state = _make_state(74.0)
    param = profile.get_parameter("step_3_yield")
    is_novel, _, _ = _check_novelty(sig, param, {param.name: state})
    assert is_novel is True


def test_novelty_not_novel_small_change(profile):
    """Prior baseline=72.8, actual=73.1 → 0.4% change < 5% → NOT novel."""
    sig = _make_internal(actual=73.1, planned=74.0)
    state = _make_state(72.8)
    param = profile.get_parameter("step_3_yield")
    is_novel, _, _ = _check_novelty(sig, param, {param.name: state})
    assert is_novel is False


# ─── Unknown parameter ────────────────────────────────────────────────────────

def test_unknown_parameter_not_relevant(profile):
    sig = _make_internal(param_id="unknown_param_xyz")
    result = assess_internal_signal(sig, profile, {})
    assert result.relevance.is_relevant is False
    assert result.severity is None


# ─── No LLM calls ─────────────────────────────────────────────────────────────

def test_rule_engine_makes_no_llm_calls(profile):
    mock_client = MagicMock()
    sig = _make_internal(actual=52.2, planned=74.0)
    # assess_internal_signal does not accept a client — it never calls one
    result = assess_internal_signal(sig, profile, {})
    mock_client.complete.assert_not_called()
    mock_client.search.assert_not_called()
    assert result.assessment_engine == "rule_engine"


# ─── _internal_to_signal hash determinism ─────────────────────────────────────

def test_internal_to_signal_deterministic():
    sig = _make_internal(actual=52.2, planned=74.0, signal_id="determinism_test")
    s1 = _internal_to_signal(sig)
    s2 = _internal_to_signal(sig)
    assert s1.raw_content_hash == s2.raw_content_hash
    assert s1.id == "determinism_test"


# ─── Default thresholds ───────────────────────────────────────────────────────

def test_default_thresholds_applied_when_no_parameter_thresholds(profile):
    """
    A parameter with category=operational and no internal_thresholds should
    get thresholds from profile.default_thresholds.yield_parameters.
    """
    from agent.domain import RiskProfileParameter
    param_no_thresh = RiskProfileParameter(
        id="test_step_yield",
        name="Test Step Yield",
        category="operational",
        risk_tier="HIGH",
        applies_to_scenarios=["our_current"],
        internal_thresholds=None,
    )
    thresholds = profile.thresholds_for(param_no_thresh)
    assert thresholds is not None
    assert thresholds.elevated_threshold == pytest.approx(0.85)
    assert thresholds.high_threshold == pytest.approx(0.75)
    assert thresholds.critical_threshold == pytest.approx(0.65)


# ─── Corpus file integration ─────────────────────────────────────────────────

def test_corpus_internal_signals_load_and_assess(profile):
    """Load all 8 corpus internal signal files and verify basic assessment runs."""
    from agent.collector import collect_internal_signals
    corpus_dir = Path(__file__).parent.parent / "corpus" / "internal_signals"
    signals = collect_internal_signals(corpus_dir)
    assert len(signals) == 8
    for sig in signals:
        result = assess_internal_signal(sig, profile, {})
        assert result.relevance is not None
        assert result.assessment_engine == "rule_engine"
