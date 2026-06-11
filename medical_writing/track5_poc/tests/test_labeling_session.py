from labeling.labeling_models import LabelingSession
from workflow.session import SessionManager, PHASES, record_step


def _session(mode="high_quality"):
    return LabelingSession(
        session_id="t5_test01", simulation_mode=mode, program_name="Aleniglipron",
        indication="obesity", ci_twin_id="ci_glp1_obesity_fda",
        content_twin_id="molecule_aleniglipron",
    )


def test_phase_transitions():
    s = _session()
    assert s.phase == "setup"
    for phase in PHASES[1:]:
        s.phase = phase
        assert s.phase == phase
    assert PHASES == ["setup", "ci_review", "map_review", "qc", "locked", "complete"]


def test_step_timings_record_timestamps():
    s = _session()
    record_step(s, "ci_review_complete")
    record_step(s, "map_locked")
    steps = [t["step"] for t in s.step_timings]
    assert steps == ["ci_review_complete", "map_locked"]
    assert all("timestamp" in t for t in s.step_timings)


def test_gap_fill_and_backprop_counters():
    s = _session()
    s.gaps_filled_jit += 1
    s.back_propagations += 1
    assert s.gaps_filled_jit == 1
    assert s.back_propagations == 1


def test_session_persists_and_reloads(tmp_results):
    s = _session()
    s.claims_total = 5
    s.phase = "complete"
    mgr = SessionManager()
    mgr.save(s)
    loaded = mgr.load("t5_test01")
    assert loaded.claims_total == 5
    assert loaded.phase == "complete"
    assert mgr.list_sessions()[0].session_id == "t5_test01"


def test_lifecycle_completes_both_modes(tmp_results):
    mgr = SessionManager()
    for mode in ["high_quality", "low_quality"]:
        s = _session(mode)
        s.session_id = f"t5_{mode}"
        s.phase = "complete"
        s.status = "complete"
        mgr.save(s)
        assert mgr.load(f"t5_{mode}").simulation_mode == mode
