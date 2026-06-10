from labeling.draft_models import DraftReviewResult, DraftRevisionRequest
from labeling.labeling_models import LabelingSession
from workflow.session import record_step

SECTION_IDS = ["indications_usage", "clinical_studies",
               "warnings_precautions", "adverse_reactions"]


def _revisions():
    return [
        DraftRevisionRequest(request_id="r1", section_id="clinical_studies",
                             change_type="content_change", description="add responder values"),
        DraftRevisionRequest(request_id="r2", section_id="warnings_precautions",
                             change_type="content_change", description="strengthen MTC language"),
        DraftRevisionRequest(request_id="r3", section_id="indications_usage",
                             change_type="formatting", description="bullet the comorbidities"),
    ]


def test_content_change_count_isolated():
    review = DraftReviewResult(
        draft_id="draft_1", reviewer_role="regulatory_affairs",
        section_ratings={sid: 8 for sid in SECTION_IDS},
        overall_draft_quality=8, regulatory_language_quality=8,
        precedent_alignment=8, ready_for_revision=7,
        revision_requests=_revisions(),
    )
    assert len(review.revision_requests) == 3
    assert review.content_revision_count == 2


def test_section_ratings_cover_all_sections():
    review = DraftReviewResult(
        draft_id="draft_1", reviewer_role="regulatory_affairs",
        section_ratings={sid: 7 for sid in SECTION_IDS},
        overall_draft_quality=7, regulatory_language_quality=7,
        precedent_alignment=7, ready_for_revision=7,
    )
    assert set(review.section_ratings.keys()) == set(SECTION_IDS)


def test_step_timing_records_draft_review_complete():
    s = LabelingSession(
        session_id="t5_dr", simulation_mode="high_quality", program_name="Aleniglipron",
        indication="obesity", ci_twin_id="ci_glp1_obesity_fda",
        content_twin_id="molecule_aleniglipron",
    )
    record_step(s, "draft_review_complete")
    assert any(t["step"] == "draft_review_complete" for t in s.step_timings)


def test_session_draft_fields_persist():
    s = LabelingSession(
        session_id="t5_dr2", simulation_mode="high_quality", program_name="Aleniglipron",
        indication="obesity", ci_twin_id="ci_glp1_obesity_fda",
        content_twin_id="molecule_aleniglipron",
    )
    s.draft_content_revision_requests = 2
    s.draft_total_revision_requests = 3
    s.draft_overall_quality_rating = 8.0
    assert s.draft_content_revision_requests == 2
    assert s.draft_overall_quality_rating == 8.0
