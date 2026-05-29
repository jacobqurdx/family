"""
Tests for workflow session creation and processing.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import tempfile
import os
import datetime

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


def test_create_workflow_session():
    sessions_dir = make_temp_session_dir()
    mgr = WorkflowSessionManager(sessions_dir=sessions_dir)
    session = mgr.create("writer_1", "csr_efficacy_assignment", "synth_phase2_trial", "high_quality")
    assert session.session_id is not None
    assert session.status == "in_progress"
    assert session.simulation_mode == "high_quality"
    assert session.adjudication_records == []


def test_save_and_load_workflow_session():
    sessions_dir = make_temp_session_dir()
    mgr = WorkflowSessionManager(sessions_dir=sessions_dir)
    session = mgr.create("writer_1", "csr_efficacy_assignment", "synth_phase2_trial")
    session_id = session.session_id

    loaded = mgr.load(session_id)
    assert loaded.session_id == session_id
    assert loaded.writer_id == "writer_1"


def test_process_all_4_sections():
    sessions_dir = make_temp_session_dir()
    mgr = WorkflowSessionManager(sessions_dir=sessions_dir)
    session = mgr.create("writer_1", "csr_efficacy_assignment", "synth_phase2_trial", "high_quality")

    adj_mgr = AdjudicationManager()
    for i, (sid, stitle) in enumerate(zip(SECTION_IDS, SECTION_TITLES)):
        adj_mgr.record_decision(
            session=session,
            section_id=sid,
            section_title=stitle,
            decision=AdjudicationDecision.APPROVED,
            simulated_prose=f"Prose for {stitle}",
            final_prose=f"Prose for {stitle}",
            time_seconds=float(30 + i * 5),
        )

    assert len(session.adjudication_records) == 4
    mgr.save(session)


def test_complete_session():
    sessions_dir = make_temp_session_dir()
    mgr = WorkflowSessionManager(sessions_dir=sessions_dir)
    session = mgr.create("writer_1", "csr_efficacy_assignment", "synth_phase2_trial", "high_quality")

    adj_mgr = AdjudicationManager()
    for sid, stitle in zip(SECTION_IDS, SECTION_TITLES):
        adj_mgr.record_decision(
            session=session, section_id=sid, section_title=stitle,
            decision=AdjudicationDecision.APPROVED,
            simulated_prose="prose", final_prose="prose", time_seconds=30.0,
        )

    mgr.complete(session)
    assert session.status == "complete"
    assert session.completed_at is not None


def test_workflow_metrics_computed():
    sessions_dir = make_temp_session_dir()
    mgr = WorkflowSessionManager(sessions_dir=sessions_dir)
    session = mgr.create("writer_1", "csr_efficacy_assignment", "synth_phase2_trial", "high_quality")

    adj_mgr = AdjudicationManager()
    for sid, stitle in zip(SECTION_IDS, SECTION_TITLES):
        adj_mgr.record_decision(
            session=session, section_id=sid, section_title=stitle,
            decision=AdjudicationDecision.APPROVED,
            simulated_prose="prose", final_prose="prose", time_seconds=30.0,
        )
    mgr.complete(session)

    evaluator = WorkflowEvaluator()
    metrics = evaluator.evaluate(session)

    assert metrics.total_sections == 4
    assert metrics.approved_count == 4
    assert metrics.revised_count == 0
    assert metrics.escalated_count == 0
    assert metrics.total_ai_time_seconds == 120.0  # 4 * 30 sec
    assert metrics.time_savings_pct > 0  # 120 sec AI vs 120 min baseline


def test_list_workflow_sessions():
    sessions_dir = make_temp_session_dir()
    mgr = WorkflowSessionManager(sessions_dir=sessions_dir)
    s1 = mgr.create("writer_1", "csr_efficacy_assignment", "twin_1")
    s2 = mgr.create("writer_2", "csr_efficacy_assignment", "twin_2")

    sessions = mgr.list_sessions()
    ids = [s.session_id for s in sessions]
    assert s1.session_id in ids
    assert s2.session_id in ids
