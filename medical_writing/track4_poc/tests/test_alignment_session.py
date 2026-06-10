from workflow.session import (
    AlignmentSession, ParticipantRecord, SessionPhase, SessionManager,
)

ROLES = ["regulatory_affairs", "medical_writing", "clinical_science", "clinical_operations"]


def _session(mode="high_quality"):
    return AlignmentSession(
        session_id="t4_test01", simulation_mode=mode, document_type="eop2_briefing",
        content_twin_id="molecule_aleniglipron", structure_twin_id="structure_eop2_fda",
        participants=[ParticipantRecord(participant_id=f"{r}_p1", role=r) for r in ROLES],
    )


def test_session_has_all_four_roles():
    s = _session()
    assert len(s.participants) == 4
    assert {p.role for p in s.participants} == set(ROLES)


def test_phase_transitions():
    s = _session()
    assert s.phase == SessionPhase.SETUP
    for phase in [SessionPhase.RA_REVIEW, SessionPhase.ALIGNMENT,
                  SessionPhase.LOCKED, SessionPhase.HANDOFF,
                  SessionPhase.POST_PROSE_REVIEW, SessionPhase.COMPLETE]:
        s.phase = phase
        assert s.phase == phase


def test_step_timings_record_start_and_end():
    s = _session()
    t = s.start_step("ra_review")
    assert t.started_at is not None and t.completed_at is None
    assert t.duration_minutes is None
    closed = s.complete_step("ra_review")
    assert closed is t
    assert closed.completed_at is not None
    assert closed.duration_minutes is not None
    # closing a step that isn't open returns None
    assert s.complete_step("ra_review") is None


def test_session_persists_and_reloads(tmp_dirs):
    s = _session()
    s.start_step("alignment_session")
    s.complete_step("alignment_session")
    s.gaps_detected = 5
    mgr = SessionManager()
    mgr.save(s)
    loaded = mgr.load("t4_test01")
    assert loaded.gaps_detected == 5
    assert len(loaded.participants) == 4
    assert loaded.step_timings[0].duration_minutes is not None
    assert mgr.list_sessions()[0].session_id == "t4_test01"


def test_lifecycle_completes_in_both_modes(tmp_dirs):
    for mode in ["high_quality", "low_quality"]:
        s = _session(mode)
        s.session_id = f"t4_{mode}"
        s.phase = SessionPhase.COMPLETE
        s.status = "complete"
        SessionManager().save(s)
        loaded = SessionManager().load(f"t4_{mode}")
        assert loaded.status == "complete"
        assert loaded.simulation_mode == mode
