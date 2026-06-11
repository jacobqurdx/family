import datetime

from labeling.labeling_models import LabelingSession, LabelingSurveyResponse
from workflow.survey import submit_survey
from workflow.evaluator import LabelingEvaluator


def _session(mode, score, with_timing=True):
    s = LabelingSession(
        session_id=f"t5_{mode}", simulation_mode=mode, program_name="Aleniglipron",
        indication="obesity", ci_twin_id="ci_glp1_obesity_fda",
        content_twin_id="molecule_aleniglipron",
        claims_total=5, claims_high=4, claims_medium=1,
    )
    if with_timing:
        s.step_timings = [
            {"step": "map_generation_start", "timestamp": "2026-06-09T10:00:00"},
            {"step": "map_locked", "timestamp": "2026-06-09T10:18:00"},
        ]
    submit_survey(s, LabelingSurveyResponse(
        participant_id="ra_reviewer_1", role="regulatory_affairs",
        process_preference=score, ci_summary_quality=score, achievability_accuracy=score,
        risk_note_quality=score, overall_confidence=score, time_saved_rating=score,
        would_use_in_production="yes",
    ))
    return s


def test_all_survey_fields_present():
    m = LabelingEvaluator().evaluate_session(_session("high_quality", 8))
    for field in ["process_preference", "ci_summary_quality", "achievability_accuracy",
                  "risk_note_quality", "overall_confidence", "time_saved_rating",
                  "would_use_in_production"]:
        assert field in m
    assert m["process_preference"] == 8


def test_elapsed_minutes_computed():
    m = LabelingEvaluator().evaluate_session(_session("high_quality", 8))
    assert m["elapsed_minutes"] == 18.0


def test_elapsed_none_without_lock():
    s = _session("high_quality", 8, with_timing=False)
    m = LabelingEvaluator().evaluate_session(s)
    assert m["elapsed_minutes"] is None


def test_to_dataframe_columns():
    df = LabelingEvaluator().to_dataframe([_session("high_quality", 8), _session("low_quality", 5)])
    assert len(df) == 2
    for col in ["session_id", "simulation_mode", "process_preference", "elapsed_minutes"]:
        assert col in df.columns


def test_high_quality_higher_ratings():
    ev = LabelingEvaluator()
    hq = ev.evaluate_session(_session("high_quality", 8))
    lq = ev.evaluate_session(_session("low_quality", 5))
    for field in ["process_preference", "overall_confidence", "achievability_accuracy"]:
        assert hq[field] > lq[field]
