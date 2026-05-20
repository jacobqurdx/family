from __future__ import annotations
import hashlib
from pathlib import Path
from unittest.mock import patch
import pytest

from agent.assessor import assess_signal, _step_metacognition
from agent.adjudicator import is_interactive, adjudicate_severity, adjudicate_impact
from agent.domain import (
    Signal, SignalSourceType, SeverityResult, ImpactResult, MetacognitionResult,
    SeverityTier, RiskVectorType,
)
from agent.state import SignalStateStore


def _make_signal(content: str, signal_id: str = "test_sig") -> Signal:
    return Signal(
        id=signal_id,
        source_type=SignalSourceType.FILE,
        source_name="Test Source",
        source_url="https://example.com",
        collected_at="2026-05-15T10:00:00+00:00",
        raw_content=content,
        raw_content_hash=hashlib.sha256(content.encode()).hexdigest(),
    )


def _make_severity(tier: SeverityTier = SeverityTier.HIGH) -> SeverityResult:
    return SeverityResult(
        severity=tier,
        severity_reasoning="Test reasoning",
        risk_vector_type=RiskVectorType.TARIFF_ESCALATION,
        affected_geography="CN",
        affected_cdmo_node_name=None,
        prompt_version="1.0.0",
    )


def _make_impact() -> ImpactResult:
    return ImpactResult(
        estimated_cost_impact_per_kg=115.84,
        estimated_cost_impact_reasoning="Test cost reasoning",
        estimated_timeline_impact_weeks=None,
        estimated_timeline_reasoning="",
        confidence="high",
        caveats=[],
        prompt_version="1.0.0",
    )


# --- _step_metacognition ---

def test_metacognition_step_returns_certain(stub_client):
    signal = _make_signal("WuXi STA tariff 55% confirmed final rule federal register")
    result = _step_metacognition(
        step="severity",
        signal=signal,
        assessment_dict={"severity": "HIGH", "severity_reasoning": "Confirmed tariff"},
        context_summary="Base cost: $5208/kg",
        client=stub_client,
        cache_dir=None,
    )
    assert result.grade in ("CERTAIN", "UNCERTAIN")
    assert result.step == "severity"
    assert isinstance(result.confidence, float)
    assert 0.0 <= result.confidence <= 1.0


def test_metacognition_step_uncertain_for_hedged_content(stub_client):
    signal = _make_signal(
        "Reportedly, sources say an amendment has not yet been confirmed. "
        "Bipartisan support but has not been voted on."
    )
    result = _step_metacognition(
        step="severity",
        signal=signal,
        assessment_dict={"severity": "HIGH"},
        context_summary="Base cost: $5208/kg",
        client=stub_client,
        cache_dir=None,
    )
    assert result.grade == "UNCERTAIN"


# --- assess_signal metacognition fields ---

def test_assess_signal_populates_severity_metacognition(stub_client, sensitivity_context, tmp_path):
    signal = _make_signal("WuXi STA tariff 55% confirmed final rule federal register")
    store = SignalStateStore(tmp_path / "state.json")
    store.initialise_from_sensitivity_context(sensitivity_context)

    result = assess_signal(
        signal, sensitivity_context, store.all(), stub_client,
        interactive=False,
    )

    if result.severity is not None:
        assert result.severity_metacognition is not None
        assert result.severity_metacognition.step == "severity"
        assert result.severity_metacognition.grade in ("CERTAIN", "UNCERTAIN")


def test_assess_signal_no_metacognition_for_irrelevant(stub_client, sensitivity_context, tmp_path):
    signal = _make_signal("semiconductor cold chain unrelated oncology mckinsey report")
    store = SignalStateStore(tmp_path / "state.json")
    store.initialise_from_sensitivity_context(sensitivity_context)

    result = assess_signal(
        signal, sensitivity_context, store.all(), stub_client,
        interactive=False,
    )

    assert result.severity is None
    assert result.severity_metacognition is None
    assert result.impact_metacognition is None


# --- adjudicator unit tests ---

def test_is_interactive_false_in_test(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert is_interactive() is False


def test_adjudicate_severity_accept(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "")
    severity = _make_severity(SeverityTier.HIGH)
    meta = MetacognitionResult(
        grade="UNCERTAIN", confidence=0.7, uncertainty_flags=["test flag"],
        reasoning="borderline", step="severity", prompt_version="1.0.0",
    )
    signal = _make_signal("some content")

    new_severity, new_meta = adjudicate_severity(severity, meta, signal)

    assert new_severity.severity == SeverityTier.HIGH
    assert new_meta.adjudicated is True
    assert new_meta.adjudicated_by == "human:accepted"


def test_adjudicate_severity_override(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "4")  # CRITICAL = index 4
    severity = _make_severity(SeverityTier.HIGH)
    meta = MetacognitionResult(
        grade="UNCERTAIN", confidence=0.7, uncertainty_flags=[],
        reasoning="borderline", step="severity", prompt_version="1.0.0",
    )
    signal = _make_signal("some content")

    new_severity, new_meta = adjudicate_severity(severity, meta, signal)

    assert new_severity.severity == SeverityTier.CRITICAL
    assert new_meta.adjudicated is True
    assert "overridden" in (new_meta.adjudicated_by or "")


def test_adjudicate_impact_accept(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "")
    impact = _make_impact()
    meta = MetacognitionResult(
        grade="UNCERTAIN", confidence=0.6, uncertainty_flags=["cost not traced"],
        reasoning="figures not in sensitivity data", step="impact", prompt_version="1.0.0",
    )
    signal = _make_signal("some content")

    new_impact, new_meta = adjudicate_impact(impact, meta, signal)

    assert new_impact.estimated_cost_impact_per_kg == 115.84
    assert new_meta.adjudicated is True
    assert new_meta.adjudicated_by == "human:accepted"


def test_adjudicate_impact_override_cost(monkeypatch):
    inputs = iter(["c", "200.0"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    impact = _make_impact()
    meta = MetacognitionResult(
        grade="UNCERTAIN", confidence=0.6, uncertainty_flags=[],
        reasoning="uncertain", step="impact", prompt_version="1.0.0",
    )
    signal = _make_signal("some content")

    new_impact, new_meta = adjudicate_impact(impact, meta, signal)

    assert new_impact.estimated_cost_impact_per_kg == 200.0
    assert new_meta.adjudicated is True
    assert "overridden" in (new_meta.adjudicated_by or "")
