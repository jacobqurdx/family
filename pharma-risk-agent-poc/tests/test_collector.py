import json
import pytest
from pathlib import Path

from agent.collector import collect_from_files
from agent.domain import SignalSourceType


def test_collect_from_files_json(tmp_path):
    for i in range(2):
        (tmp_path / f"signal_{i}.json").write_text(json.dumps({
            "id": f"sig_{i}",
            "content": f"Signal content number {i} about tariff.",
            "source_name": "Test Source",
            "source_url": f"https://example.com/{i}",
            "collected_at": "2026-05-15T10:00:00+00:00",
        }))
    signals = collect_from_files(tmp_path)
    assert len(signals) == 2
    assert all(s.source_type == SignalSourceType.FILE for s in signals)


def test_collect_from_files_txt(tmp_path):
    (tmp_path / "signal_a.txt").write_text("Plain text signal content about WuXi.")
    signals = collect_from_files(tmp_path)
    assert len(signals) == 1
    assert signals[0].source_type == SignalSourceType.FILE
    assert signals[0].id == "signal_a"


def test_collect_from_files_deduplication(tmp_path):
    same_content = "Same content for both files to test collector behavior."
    (tmp_path / "file_one.txt").write_text(same_content)
    (tmp_path / "file_two.txt").write_text(same_content)
    signals = collect_from_files(tmp_path)
    # File mode does NOT deduplicate — both files are returned
    assert len(signals) == 2


def test_signal_id_from_json(tmp_path):
    (tmp_path / "my_signal.json").write_text(json.dumps({
        "id": "my_signal",
        "content": "Some content here.",
        "source_name": "Reuters",
        "collected_at": "2026-05-01T00:00:00+00:00",
    }))
    signals = collect_from_files(tmp_path)
    assert len(signals) == 1
    assert signals[0].id == "my_signal"
