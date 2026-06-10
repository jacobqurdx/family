from workflow.session import AlignmentSession, ParticipantRecord, SurveyResponse
from workflow.survey import submit_survey, SURVEY_QUESTIONS
from workflow.evaluator import WorkflowEvaluator


def _session():
    return AlignmentSession(
        session_id="t4_s", simulation_mode="high_quality",
        document_type="eop2_briefing",
        content_twin_id="molecule_aleniglipron",
        structure_twin_id="structure_eop2_fda",
        participants=[
            ParticipantRecord(participant_id="ra_p1", role="regulatory_affairs"),
            ParticipantRecord(participant_id="mw_p1", role="medical_writing"),
        ],
    )


def _response(role, pid, base):
    return SurveyResponse(
        participant_id=pid, role=role,
        alignment_process_preference=base,
        spec_quality_rating=base,
        qc_findings_utility=base - 1,
        role_review_clarity=base + 1,
        confidence_in_document=base,
        likelihood_of_content_revisions=base,
        what_worked="spec-first alignment",
        what_didnt_work="",
    )


def test_survey_stored_and_participant_flagged():
    s = _session()
    submit_survey(s, _response("regulatory_affairs", "ra_p1", 8))
    assert len(s.survey_responses) == 1
    assert s.get_participant("regulatory_affairs").survey_completed is True
    assert s.get_participant("medical_writing").survey_completed is False


def test_survey_question_fields_match_model():
    fields = {q[0] for q in SURVEY_QUESTIONS}
    model_fields = set(SurveyResponse.model_fields.keys())
    assert fields <= model_fields


def test_evaluator_averages_across_responses():
    s = _session()
    submit_survey(s, _response("regulatory_affairs", "ra_p1", 8))   # preference 8
    submit_survey(s, _response("medical_writing", "mw_p1", 6))      # preference 6
    metrics = WorkflowEvaluator().evaluate_session(s)
    assert metrics["avg_alignment_process_preference"] == 7.0
    assert metrics["avg_role_review_clarity"] == 8.0   # (9 + 7) / 2
    assert metrics["survey_completion_rate"] == 1.0
