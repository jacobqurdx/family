import pytest

import config
from twins.registry import TwinRegistry
from generation.content_spec_generator import ContentSpecGenerator
from governance.versioning import VersionManager
from workflow.handoff import HandoffManager


def _locked_spec():
    config.SIMULATION_MODE = "high_quality"
    pair = TwinRegistry().resolve("structure_eop2_fda")
    spec = ContentSpecGenerator().generate(pair)
    VersionManager().version_lock(spec, "regulatory_affairs", timestamp="20260609_1300")
    return spec


def test_handoff_serialises_all_five_sections(tmp_dirs):
    spec = _locked_spec()
    handoff = HandoffManager().create("t4_h1", spec, ra_notes="note")
    assert len(handoff.sections) == 5
    section_ids = {s["section_id"] for s in handoff.sections}
    assert "regulatory_questions" in section_ids


def test_handoff_locked_metadata_populated(tmp_dirs):
    spec = _locked_spec()
    handoff = HandoffManager().create("t4_h2", spec)
    assert handoff.locked_at is not None
    assert handoff.locked_by == "regulatory_affairs"
    assert handoff.locked_spec_version == "v20260609_1300"


def test_handoff_round_trips_via_manager(tmp_dirs):
    spec = _locked_spec()
    mgr = HandoffManager()
    created = mgr.create("t4_h3", spec, ra_notes="priority on CV safety",
                         priority_sections=["cardiovascular_safety"])
    loaded = mgr.load(created.handoff_id)
    assert loaded.handoff_id == created.handoff_id
    assert loaded.ra_notes == "priority on CV safety"
    assert loaded.priority_sections == ["cardiovascular_safety"]
    assert len(loaded.sections) == 5


def test_unlocked_spec_raises(tmp_dirs):
    config.SIMULATION_MODE = "high_quality"
    pair = TwinRegistry().resolve("structure_eop2_fda")
    spec = ContentSpecGenerator().generate(pair)  # not locked
    with pytest.raises(ValueError):
        HandoffManager().create("t4_h4", spec)


def test_qc_findings_summary_counts(tmp_dirs):
    from review.finding_models import QCFinding
    spec = _locked_spec()
    findings = [
        QCFinding(finding_id="f1", section_id="x", pass_number=2,
                  severity="blocking", category="prior_crl_concern", description="d"),
        QCFinding(finding_id="f2", section_id="x", pass_number=4,
                  severity="minor", category="low_confidence", description="d"),
    ]
    handoff = HandoffManager().create("t4_h5", spec, qc_findings=findings)
    assert handoff.qc_findings_summary == {"blocking": 1, "major": 0, "minor": 1}
