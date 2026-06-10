import uuid

from workflow.session import (
    AlignmentSession, ParticipantRecord, SurveyResponse, ContentRevisionRequest,
)
from workflow.survey import submit_survey
from workflow.evaluator import WorkflowEvaluator


def _session(mode, revisions, survey_score):
    s = AlignmentSession(
        session_id=f"t4_{uuid.uuid4().hex[:6]}", simulation_mode=mode,
        document_type="eop2_briefing",
        content_twin_id="molecule_aleniglipron",
        structure_twin_id="structure_eop2_fda",
        participants=[
            ParticipantRecord(participant_id="ra_p1", role="regulatory_affairs"),
        ],
    )
    for i in range(revisions):
        s.content_revision_requests.append(ContentRevisionRequest(
            request_id=f"rev_{i}", requesting_role="clinical_science",
            section_id="phase2_results_summary", description="change",
            change_type="content_change",
        ))
    # one non-content request — must not count against the hypothesis
    s.content_revision_requests.append(ContentRevisionRequest(
        request_id="rev_fmt", requesting_role="medical_writing",
        section_id="background_rationale", description="formatting",
        change_type="formatting",
    ))
    submit_survey(s, SurveyResponse(
        participant_id="ra_p1", role="regulatory_affairs",
        alignment_process_preference=survey_score,
        spec_quality_rating=survey_score,
        qc_findings_utility=survey_score,
        role_review_clarity=survey_score,
        confidence_in_document=survey_score,
        likelihood_of_content_revisions=survey_score,
    ))
    return s


def test_only_content_changes_count():
    s = _session("high_quality", revisions=2, survey_score=8)
    metrics = WorkflowEvaluator().evaluate_session(s)
    # 2 content changes + 1 formatting logged, only 2 count
    assert metrics["content_revision_requests"] == 2


def test_high_quality_session_meets_success_criteria():
    s = _session("high_quality", revisions=0, survey_score=8)
    m = WorkflowEvaluator().evaluate_session(s)
    assert m["content_revision_requests"] == 0
    assert m["avg_alignment_process_preference"] >= 7.0
    assert m["avg_role_review_clarity"] >= 7.0
    assert m["avg_qc_findings_utility"] >= 6.5


def test_compare_modes_delta_and_validation():
    hq = [_session("high_quality", revisions=0, survey_score=8)]
    lq = [_session("low_quality", revisions=3, survey_score=5)]
    cmp = WorkflowEvaluator().compare_modes(hq, lq)

    assert cmp["high_quality"]["avg_content_revisions"] == 0
    assert cmp["low_quality"]["avg_content_revisions"] == 3
    assert cmp["delta"]["content_revisions"] == 3
    assert cmp["delta"]["survey_preference"] == 3.0
    assert cmp["validation"]["high_quality_fewer_revisions"] is True
    assert cmp["validation"]["high_quality_higher_preference"] is True


def test_to_dataframe():
    sessions = [
        _session("high_quality", 0, 8),
        _session("low_quality", 3, 5),
    ]
    df = WorkflowEvaluator().to_dataframe(sessions)
    assert len(df) == 2
    assert "content_revision_requests" in df.columns
    assert df["content_revision_requests"].tolist() == [0, 3]
