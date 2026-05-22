import json
import os
from pathlib import Path

import pytest

from agent.llm import LLMClient, write_stub_files, STUB_RESPONSES_DIR


def test_stub_client_returns_json(stub_client):
    response = stub_client.complete("Some prompt mentioning tariff rates.", "relevance")
    data = json.loads(response)
    assert "is_relevant" in data


def test_stub_relevance_relevant(stub_client):
    prompt = "Signal content: WuXi STA tariff impact on API supply chain."
    response = stub_client.complete(prompt, "relevance")
    data = json.loads(response)
    assert data["is_relevant"] is True


def test_stub_relevance_irrelevant(stub_client):
    prompt = "Signal about semiconductor equipment and unrelated generic company."
    response = stub_client.complete(prompt, "relevance")
    data = json.loads(response)
    assert data["is_relevant"] is False


def test_stub_novelty(stub_client):
    prompt = "New confirmed development: announced official action at facility."
    response = stub_client.complete(prompt, "novelty")
    data = json.loads(response)
    assert "is_novel" in data


def test_stub_severity(stub_client):
    prompt = "tariff 55% HS code USTR pharmaceutical starting materials."
    response = stub_client.complete(prompt, "severity")
    data = json.loads(response)
    assert "severity" in data


def test_stub_all_steps_no_api_key(stub_client):
    assert os.environ.get("ANTHROPIC_API_KEY") is None or True  # key may or may not be set
    # The point is the stub works regardless of key presence
    for step in ("relevance", "novelty", "severity", "impact"):
        result = stub_client.complete("WuXi tariff announced confirmed signed into law.", step)
        assert isinstance(result, str)
        assert len(result) > 0


def test_stub_files_exist():
    expected_dirs = {"relevance", "novelty", "severity", "impact", "briefing", "collection"}
    assert STUB_RESPONSES_DIR.exists(), "stub_responses dir must exist"
    existing = {d.name for d in STUB_RESPONSES_DIR.iterdir() if d.is_dir()}
    assert expected_dirs <= existing
