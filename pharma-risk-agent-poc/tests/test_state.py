import json
import pytest
from pathlib import Path

from agent.domain import (
    AssessedSignal, NoveltyResult, RelevanceResult, Signal, SignalSourceType
)
from agent.state import SignalStateStore


def test_initialise_from_context(sensitivity_context, tmp_state_file):
    store = SignalStateStore(tmp_state_file)
    store.initialise_from_sensitivity_context(sensitivity_context)
    states = store.all()
    expected_params = {w.parameter_name for w in sensitivity_context.signal_priority_weights}
    assert expected_params == set(states.keys())


def test_state_has_correct_fields(sensitivity_context, tmp_state_file):
    store = SignalStateStore(tmp_state_file)
    store.initialise_from_sensitivity_context(sensitivity_context)
    for state in store.all().values():
        assert hasattr(state, "parameter_name")
        assert hasattr(state, "risk_level")
        assert hasattr(state, "current_state_summary")
        assert isinstance(state.current_state_summary, str)
        assert len(state.current_state_summary) > 0


def test_save_and_reload(sensitivity_context, tmp_state_file):
    store = SignalStateStore(tmp_state_file)
    store.initialise_from_sensitivity_context(sensitivity_context)
    original_keys = set(store.all().keys())

    reloaded = SignalStateStore(tmp_state_file)
    assert set(reloaded.all().keys()) == original_keys


def test_apply_novelty_updates(sensitivity_context, tmp_state_file):
    store = SignalStateStore(tmp_state_file)
    store.initialise_from_sensitivity_context(sensitivity_context)

    param_name = sensitivity_context.signal_priority_weights[3].parameter_name  # "Starting Material A"
    new_summary = "Updated: supply disrupted due to FDA enforcement action."

    signal = Signal(
        id="upd_001",
        source_type=SignalSourceType.FILE,
        source_name="Test",
        source_url="https://example.com",
        collected_at="2026-05-15T10:00:00+00:00",
        raw_content="content",
        raw_content_hash="hash001",
    )
    novelty = NoveltyResult(
        is_novel=True,
        novelty_reasoning="New development confirmed.",
        updated_parameter_states=[{
            "parameter_name": param_name,
            "new_state_summary": new_summary,
            "new_baseline_value": None,
            "new_baseline_value_unit": None,
            "change_direction": "disrupted",
        }],
        prompt_version="1",
    )
    assessed = AssessedSignal(
        signal=signal,
        relevance=RelevanceResult(
            is_relevant=True,
            relevant_parameters=[param_name],
            relevance_reasoning="relevant",
            prompt_version="1",
        ),
        novelty=novelty,
        severity=None,
        impact=None,
        recommended_actions=[],
    )

    store.apply_novelty_updates(assessed, param_name)
    state = store.get(param_name)
    assert state is not None
    assert state.current_state_summary == new_summary
    assert state.last_known_change_direction == "disrupted"


def test_get_unknown_param(sensitivity_context, tmp_state_file):
    store = SignalStateStore(tmp_state_file)
    store.initialise_from_sensitivity_context(sensitivity_context)
    assert store.get("nonexistent_parameter_xyz") is None
