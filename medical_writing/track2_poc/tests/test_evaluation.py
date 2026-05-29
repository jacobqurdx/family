"""
Tests for workflow/evaluation.py
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import tempfile
import os

from workflow.session import WorkflowSessionManager
from workflow.adjudication import AdjudicationManager
from workflow.models import AdjudicationDecision, SurveyRating
from workflow.evaluation import WorkflowEvaluator


def make_temp_session_dir():
    tmp = tempfile.mkdtemp()
    return os.path.join(tmp, "workflow_sessions")


SECTION_IDS = [
    "primary_efficacy_results",
    "statistical_methods",
    "eligibility_summary",
    "study_design_overview",
]
SECTION_TITLES = [
    "Primary Efficacy Results",
    "Statistical Methods",
    "Eligibility Summary",
    "Study Design Overview",
]


def make_completed_session(mode: str, time_seconds_per_section: float, survey_scores=None):
    """Helper to create a completed session with adjudication records and optional survey."""
    sessions_dir = make_temp_session_dir()
    mgr = WorkflowSessionManager(sessions_dir=sessions_dir)
    session = mgr.create("writer_test", "csr_efficacy_assignment", "synth_phase2_trial", mode)

    adj_mgr = AdjudicationManager()
    for sid, stitle in zip(SECTION_IDS, SECTION_TITLES):
        adj_mgr.record_decision(
            session=session, section_id=sid, section_title=stitle,
            decision=AdjudicationDecision.APPROVED,
            simulated_prose="prose", final_prose="prose",
            time_seconds=time_seconds_per_section,
        )

    if survey_scores:
        session.survey = SurveyRating(
            overall_experience=survey_scores[0],
            time_savings_perceived=survey_scores[1],
            document_quality=survey_scores[2],
            would_use_again=survey_scores[0] >= 7,
        )

    mgr.complete(session)
    return session, mgr


def test_high_quality_time_savings():
    """High quality session with low AI time should show >25% savings vs 120 min baseline."""
    session, _ = make_completed_session("high_quality", time_seconds_per_section=60.0)
    evaluator = WorkflowEvaluator()
    metrics = evaluator.evaluate(session)

    # 4 sections * 60 sec = 240 sec = 4 min actual
    # 120 min baseline → savings = (1 - 4/120) * 100 = 96.7%
    assert metrics.time_savings_pct > 25.0
    assert metrics.simulation_mode == "high_quality"
    assert metrics.total_sections == 4


def test_low_quality_higher_time():
    """Low quality session with longer review time shows lower (but still positive) savings."""
    # Simulate writer spending more time revising low quality output: 20 min per section
    session, _ = make_completed_session("low_quality", time_seconds_per_section=1200.0)
    evaluator = WorkflowEvaluator()
    metrics = evaluator.evaluate(session)

    # 4 * 1200 sec = 4800 sec = 80 min actual vs 120 min baseline
    assert metrics.simulation_mode == "low_quality"
    assert metrics.time_savings_pct >= 0  # Should still be positive (80 < 120)


def test_adoption_threshold_met_high_survey():
    """When avg survey score >= 7, adoption_threshold_met should be True."""
    session, _ = make_completed_session("high_quality", 60.0, survey_scores=[8, 8, 8])
    evaluator = WorkflowEvaluator()
    metrics = evaluator.evaluate(session)

    assert metrics.avg_survey_score == pytest.approx(8.0, abs=0.1)
    assert metrics.adoption_threshold_met is True


def test_adoption_threshold_not_met_low_survey():
    """When avg survey score < 7, adoption_threshold_met should be False."""
    session, _ = make_completed_session("low_quality", 1200.0, survey_scores=[5, 5, 5])
    evaluator = WorkflowEvaluator()
    metrics = evaluator.evaluate(session)

    assert metrics.avg_survey_score == pytest.approx(5.0, abs=0.1)
    assert metrics.adoption_threshold_met is False


def test_no_survey_adoption_threshold():
    """Without survey, adoption_threshold_met is False and avg_survey_score is None."""
    session, _ = make_completed_session("high_quality", 60.0)
    evaluator = WorkflowEvaluator()
    metrics = evaluator.evaluate(session)

    assert metrics.avg_survey_score is None
    assert metrics.adoption_threshold_met is False


def test_approval_rate_all_approved():
    from workflow.adjudication import AdjudicationManager
    sessions_dir = make_temp_session_dir()
    mgr = WorkflowSessionManager(sessions_dir=sessions_dir)
    session = mgr.create("w1", "csr_efficacy_assignment", "twin1", "high_quality")

    adj_mgr = AdjudicationManager()
    for sid, stitle in zip(SECTION_IDS, SECTION_TITLES):
        adj_mgr.record_decision(
            session=session, section_id=sid, section_title=stitle,
            decision=AdjudicationDecision.APPROVED,
            simulated_prose="p", final_prose="p", time_seconds=30.0,
        )

    rate = adj_mgr.get_approval_rate(session)
    assert rate == 1.0


def test_approval_rate_mixed():
    from workflow.adjudication import AdjudicationManager
    sessions_dir = make_temp_session_dir()
    mgr = WorkflowSessionManager(sessions_dir=sessions_dir)
    session = mgr.create("w1", "csr_efficacy_assignment", "twin1", "low_quality")

    adj_mgr = AdjudicationManager()
    decisions = [
        AdjudicationDecision.APPROVED,
        AdjudicationDecision.REVISED,
        AdjudicationDecision.ESCALATED,
        AdjudicationDecision.APPROVED,
    ]
    for sid, stitle, dec in zip(SECTION_IDS, SECTION_TITLES, decisions):
        adj_mgr.record_decision(
            session=session, section_id=sid, section_title=stitle,
            decision=dec, simulated_prose="p", final_prose="p", time_seconds=30.0,
        )

    rate = adj_mgr.get_approval_rate(session)
    assert rate == pytest.approx(0.5, abs=0.01)


def test_metrics_revised_escalated_count():
    sessions_dir = make_temp_session_dir()
    mgr = WorkflowSessionManager(sessions_dir=sessions_dir)
    session = mgr.create("w1", "csr_efficacy_assignment", "twin1", "low_quality")

    adj_mgr = AdjudicationManager()
    decisions = [
        AdjudicationDecision.APPROVED,
        AdjudicationDecision.REVISED,
        AdjudicationDecision.REVISED,
        AdjudicationDecision.ESCALATED,
    ]
    for sid, stitle, dec in zip(SECTION_IDS, SECTION_TITLES, decisions):
        adj_mgr.record_decision(
            session=session, section_id=sid, section_title=stitle,
            decision=dec, simulated_prose="p", final_prose="p", time_seconds=60.0,
        )

    evaluator = WorkflowEvaluator()
    metrics = evaluator.evaluate(session)

    assert metrics.approved_count == 1
    assert metrics.revised_count == 2
    assert metrics.escalated_count == 1
