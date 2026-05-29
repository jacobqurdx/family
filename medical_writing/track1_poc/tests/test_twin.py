import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.twin import DigitalTwin
from core.models import ElementStatus


@pytest.fixture
def twin():
    return DigitalTwin.load("synth_phase2_trial")


@pytest.fixture
def empty_twin():
    return DigitalTwin.new("test_twin", "protocol", "Test Trial")


def test_load_twin(twin):
    assert twin.trial_name == "STRUCT-101 Phase 2 Study"
    assert twin.schema_id == "protocol"


def test_get_value(twin):
    val = twin.get_value("drug_name")
    assert val == "STR-4021"


def test_get_missing_element_returns_none(twin):
    assert twin.get_value("nonexistent_element") is None


def test_set_element(empty_twin):
    empty_twin.set("drug_name", "TEST-001")
    assert empty_twin.get_value("drug_name") == "TEST-001"
    assert empty_twin.get("drug_name").status == ElementStatus.VERIFIED


def test_set_inferred(empty_twin):
    empty_twin.set_inferred("statistical_analysis_primary", "MMRM of HbA1c", "primary_analysis_type")
    el = empty_twin.get("statistical_analysis_primary")
    assert el.status == ElementStatus.INFERRED
    assert el.source == "inferred_from:primary_analysis_type"


def test_override_with_justification(empty_twin):
    empty_twin.set("primary_endpoint", "change from baseline in HbA1c")
    empty_twin.override(
        "primary_endpoint",
        "change from baseline in FPG",
        justification="Team decision to use FPG as primary",
        modified_by="medical_writer_1"
    )
    el = empty_twin.get("primary_endpoint")
    assert el.status == ElementStatus.OVERRIDDEN
    assert el.override_justification == "Team decision to use FPG as primary"
    assert el.value == "change from baseline in FPG"


def test_diff_identical_twins(twin):
    twin2 = DigitalTwin.load("synth_phase2_trial")
    diffs = twin.diff(twin2)
    assert diffs == []


def test_diff_detects_changed_element(twin, empty_twin):
    empty_twin.set("drug_name", "DIFFERENT-999")
    diffs = twin.diff(empty_twin)
    element_ids = [d["element_id"] for d in diffs]
    assert "drug_name" in element_ids


def test_completeness(twin):
    required_ids = ["drug_name", "indication", "primary_endpoint", "study_phase"]
    stats = twin.completeness(required_ids)
    assert stats["total"] == 4
    assert stats["populated"] == 4
    assert stats["completeness_pct"] == 100.0


def test_completeness_partial(empty_twin):
    empty_twin.set("drug_name", "X")
    stats = empty_twin.completeness(["drug_name", "indication", "primary_endpoint"])
    assert stats["populated"] == 1
    assert stats["completeness_pct"] == pytest.approx(33.3, abs=0.1)


def test_get_section_data(twin):
    data = twin.get_section_data(["drug_name", "indication", "study_phase"])
    assert data["drug_name"] == "STR-4021"
    assert data["indication"] is not None
    assert data["study_phase"] == "Phase 2"


def test_save_and_reload(empty_twin, tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "TWINS_DIR", str(tmp_path))
    empty_twin.set("drug_name", "SAVED-001")
    empty_twin.save()
    reloaded = DigitalTwin.load("test_twin")
    assert reloaded.get_value("drug_name") == "SAVED-001"
