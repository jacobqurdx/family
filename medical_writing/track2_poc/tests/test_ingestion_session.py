"""
Tests for ingestion session flow (stub mode).
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import tempfile
import os

from ingestion.ingestion_session import IngestionSessionManager
from ingestion.layer_runner import LayerRunner


def make_temp_session_dir():
    tmp = tempfile.mkdtemp()
    return os.path.join(tmp, "sessions")


def test_create_session():
    sessions_dir = make_temp_session_dir()
    mgr = IngestionSessionManager(sessions_dir=sessions_dir)
    session = mgr.create("/tmp/test.docx", "synth_phase2_trial", "protocol", "writer_test")
    assert session.session_id is not None
    assert session.current_layer == 0
    assert session.status == "in_progress"
    assert session.total_layers == 9


def test_save_and_load_session():
    sessions_dir = make_temp_session_dir()
    mgr = IngestionSessionManager(sessions_dir=sessions_dir)
    session = mgr.create("/tmp/test.docx", "synth_phase2_trial", "protocol", "writer_test")
    session_id = session.session_id

    loaded = mgr.load(session_id)
    assert loaded.session_id == session_id
    assert loaded.twin_id == "synth_phase2_trial"


def test_extract_layer_0_stub():
    sessions_dir = make_temp_session_dir()
    mgr = IngestionSessionManager(sessions_dir=sessions_dir)
    session = mgr.create("/tmp/test.docx", "synth_phase2_trial", "protocol", "writer_test")

    runner = LayerRunner(use_stub=True)
    result = runner.run_extraction(session, None)
    assert result.layer_index == 0
    assert len(result.extracted_nodes) == 12
    mgr.save(session)


def test_commit_all_confirmed_advances_layer():
    sessions_dir = make_temp_session_dir()
    mgr = IngestionSessionManager(sessions_dir=sessions_dir)
    session = mgr.create("/tmp/test.docx", "synth_phase2_trial", "protocol", "writer_test")

    runner = LayerRunner(use_stub=True)
    result = runner.run_extraction(session, None)
    runner.auto_verify_layer(session, 0, result)
    runner.advance_layer(session)

    assert session.current_layer == 1
    assert session.total_nodes_confirmed > 0
    mgr.save(session)


def test_confirmed_values_populated_after_layer_0():
    sessions_dir = make_temp_session_dir()
    mgr = IngestionSessionManager(sessions_dir=sessions_dir)
    session = mgr.create("/tmp/test.docx", "synth_phase2_trial", "protocol", "writer_test")

    runner = LayerRunner(use_stub=True)
    result = runner.run_extraction(session, None)
    runner.auto_verify_layer(session, 0, result)

    assert "drug_name" in session.confirmed_values
    assert session.confirmed_values["drug_name"] == "STR-4021"
    assert "indication" in session.confirmed_values
    assert "type 2 diabetes" in session.confirmed_values["indication"].lower()


def test_full_9_layer_ingestion():
    sessions_dir = make_temp_session_dir()
    mgr = IngestionSessionManager(sessions_dir=sessions_dir)
    session = mgr.create("/tmp/test.docx", "synth_phase2_trial", "protocol", "writer_test")

    runner = LayerRunner(use_stub=True)
    for layer_idx in range(9):
        assert session.current_layer == layer_idx
        result = runner.run_extraction(session, None)
        runner.auto_verify_layer(session, layer_idx, result)
        runner.advance_layer(session)

    assert session.status == "complete"
    assert session.current_layer == 9
    assert len(session.confirmed_values) > 0
    mgr.save(session)


def test_session_persists_confirmed_values():
    sessions_dir = make_temp_session_dir()
    mgr = IngestionSessionManager(sessions_dir=sessions_dir)
    session = mgr.create("/tmp/test.docx", "synth_phase2_trial", "protocol", "writer_test")

    runner = LayerRunner(use_stub=True)
    result = runner.run_extraction(session, None)
    runner.auto_verify_layer(session, 0, result)
    runner.advance_layer(session)
    mgr.save(session)

    # Reload and check values persist
    loaded = mgr.load(session.session_id)
    assert "drug_name" in loaded.confirmed_values
    assert loaded.confirmed_values["drug_name"] == "STR-4021"
    assert loaded.current_layer == 1


def test_list_sessions():
    sessions_dir = make_temp_session_dir()
    mgr = IngestionSessionManager(sessions_dir=sessions_dir)
    s1 = mgr.create("/tmp/a.docx", "twin1", "protocol", "writer_1")
    s2 = mgr.create("/tmp/b.docx", "twin2", "protocol", "writer_2")

    sessions = mgr.list_sessions()
    ids = [s.session_id for s in sessions]
    assert s1.session_id in ids
    assert s2.session_id in ids
