"""
Tests for ingestion verification logic.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import datetime

from ingestion.verification import (
    VerificationDecision, NodeVerificationRecord, ExtractedItem
)
from ingestion.layer_runner import LayerRunner
from ingestion.verification import IngestionSession
from core.twin import DigitalTwin
from core.models import ElementStatus


def make_session() -> IngestionSession:
    return IngestionSession(
        session_id="test_verify",
        document_filename="test.docx",
        document_path="/tmp/test.docx",
        twin_id="synth_phase2_trial",
        schema_id="protocol",
        writer_id="writer_1",
    )


def make_record(
    node_id: str,
    node_label: str,
    extracted_value,
    decision: VerificationDecision,
    corrected_value=None,
    justification=None,
    is_list_node: bool = False,
) -> NodeVerificationRecord:
    return NodeVerificationRecord(
        node_id=node_id,
        node_label=node_label,
        is_list_node=is_list_node,
        extracted_items=[ExtractedItem(item_index=0, value=extracted_value, confidence=0.9)],
        decisions=[decision],
        corrected_values=[corrected_value],
        override_justifications=[justification],
        verified_at=datetime.datetime.utcnow(),
    )


def test_confirmed_decision():
    session = make_session()
    runner = LayerRunner(use_stub=True)
    record = make_record("drug_name", "Drug Name", "STR-4021", VerificationDecision.CONFIRMED)
    runner.commit_layer_verifications(session, 0, [record])
    assert session.confirmed_values.get("drug_name") == "STR-4021"
    assert session.total_nodes_confirmed == 1


def test_confirmed_updates_twin(tmp_path):
    session = make_session()
    runner = LayerRunner(use_stub=True)
    twin = DigitalTwin.new("test_twin_verify", "protocol", "Test Trial")
    record = make_record("drug_name", "Drug Name", "STR-4021", VerificationDecision.CONFIRMED)
    runner.commit_layer_verifications(session, 0, [record], twin=twin)
    el = twin.get("drug_name")
    assert el is not None
    assert el.value == "STR-4021"
    assert el.status == ElementStatus.VERIFIED


def test_corrected_decision():
    session = make_session()
    runner = LayerRunner(use_stub=True)
    record = make_record(
        "drug_name", "Drug Name", "STR-9999",  # wrong extracted
        VerificationDecision.CORRECTED,
        corrected_value="STR-4021",
    )
    runner.commit_layer_verifications(session, 0, [record])
    assert session.confirmed_values.get("drug_name") == "STR-4021"
    assert session.total_nodes_corrected == 1


def test_corrected_updates_twin(tmp_path):
    session = make_session()
    runner = LayerRunner(use_stub=True)
    twin = DigitalTwin.new("test_twin_corr", "protocol", "Test Trial")
    record = make_record(
        "drug_name", "Drug Name", "WRONG",
        VerificationDecision.CORRECTED,
        corrected_value="STR-4021",
    )
    runner.commit_layer_verifications(session, 0, [record], twin=twin)
    el = twin.get("drug_name")
    assert el.value == "STR-4021"
    assert el.status == ElementStatus.VERIFIED


def test_overridden_decision():
    session = make_session()
    runner = LayerRunner(use_stub=True)
    record = make_record(
        "drug_name", "Drug Name", "STR-4021",
        VerificationDecision.OVERRIDDEN,
        corrected_value="STR-4021-REVISED",
        justification="Protocol amended after extraction",
    )
    runner.commit_layer_verifications(session, 0, [record])
    assert session.confirmed_values.get("drug_name") == "STR-4021-REVISED"
    assert session.total_nodes_overridden == 1


def test_overridden_updates_twin():
    session = make_session()
    runner = LayerRunner(use_stub=True)
    twin = DigitalTwin.new("test_twin_over", "protocol", "Test Trial")
    record = make_record(
        "drug_name", "Drug Name", "STR-4021",
        VerificationDecision.OVERRIDDEN,
        corrected_value="STR-4021-REVISED",
        justification="Protocol amended",
    )
    runner.commit_layer_verifications(session, 0, [record], twin=twin)
    el = twin.get("drug_name")
    assert el.value == "STR-4021-REVISED"
    assert el.status == ElementStatus.OVERRIDDEN
    assert el.override_justification == "Protocol amended"


def test_missing_with_correction():
    session = make_session()
    runner = LayerRunner(use_stub=True)
    record = make_record(
        "sponsor_name", "Sponsor Name", None,
        VerificationDecision.MISSING,
        corrected_value="Structure Therapeutics",
    )
    runner.commit_layer_verifications(session, 0, [record])
    assert session.confirmed_values.get("sponsor_name") == "Structure Therapeutics"
    assert session.total_nodes_confirmed == 1


def test_missing_without_correction():
    session = make_session()
    runner = LayerRunner(use_stub=True)
    record = make_record(
        "sponsor_name", "Sponsor Name", None,
        VerificationDecision.MISSING,
        corrected_value=None,
    )
    runner.commit_layer_verifications(session, 0, [record])
    assert "sponsor_name" not in session.confirmed_values
    assert session.total_nodes_missing == 1


def test_missing_without_correction_twin_stays_empty():
    session = make_session()
    runner = LayerRunner(use_stub=True)
    twin = DigitalTwin.new("test_twin_miss", "protocol", "Test Trial")
    record = make_record(
        "sponsor_name", "Sponsor Name", None,
        VerificationDecision.MISSING,
    )
    runner.commit_layer_verifications(session, 0, [record], twin=twin)
    el = twin.get("sponsor_name")
    assert el is None  # twin element stays unpopulated
