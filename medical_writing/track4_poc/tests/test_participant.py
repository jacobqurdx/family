from workflow.session import AlignmentSession, ParticipantRecord
from workflow.participant import (
    add_participant, start_review, complete_review, review_duration_minutes,
)


def _session():
    return AlignmentSession(
        session_id="t4_p", simulation_mode="high_quality",
        document_type="eop2_briefing",
        content_twin_id="molecule_aleniglipron",
        structure_twin_id="structure_eop2_fda",
    )


def test_review_started_at_set_on_begin():
    s = _session()
    add_participant(s, "ra_p1", "regulatory_affairs")
    p = start_review(s, "regulatory_affairs")
    assert p.review_started_at is not None
    first = p.review_started_at
    # starting again does not reset
    start_review(s, "regulatory_affairs")
    assert p.review_started_at == first


def test_decisions_made_increments():
    s = _session()
    add_participant(s, "ra_p1", "regulatory_affairs")
    add_participant(s, "cs_p1", "clinical_science")
    start_review(s, "regulatory_affairs")
    complete_review(s, "regulatory_affairs", 4)
    start_review(s, "clinical_science")
    complete_review(s, "clinical_science", 2)
    assert s.get_participant("regulatory_affairs").decisions_made == 4
    assert s.get_participant("clinical_science").decisions_made == 2
    assert s.review_decisions_total == 6


def test_review_duration_computed():
    s = _session()
    add_participant(s, "ra_p1", "regulatory_affairs")
    p = start_review(s, "regulatory_affairs")
    assert review_duration_minutes(p) is None
    complete_review(s, "regulatory_affairs", 1)
    assert review_duration_minutes(p) is not None


def test_survey_completed_flag_toggles():
    from workflow.session import SurveyResponse
    from workflow.survey import submit_survey
    s = _session()
    p = add_participant(s, "ra_p1", "regulatory_affairs")
    assert p.survey_completed is False
    submit_survey(s, SurveyResponse(
        participant_id="ra_p1", role="regulatory_affairs",
        alignment_process_preference=8, spec_quality_rating=8,
        qc_findings_utility=7, role_review_clarity=9,
        confidence_in_document=8, likelihood_of_content_revisions=8,
    ))
    assert p.survey_completed is True
    assert len(s.survey_responses) == 1


def test_add_participant_idempotent_per_role():
    s = _session()
    p1 = add_participant(s, "ra_p1", "regulatory_affairs")
    p2 = add_participant(s, "ra_p2", "regulatory_affairs")
    assert p1 is p2
    assert len(s.participants) == 1
