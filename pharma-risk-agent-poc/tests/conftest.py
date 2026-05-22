import pytest
from pathlib import Path
from agent.domain import Signal, SignalSourceType
from agent.llm import LLMClient

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
CORPUS_DIR = Path(__file__).parent.parent / "corpus"


@pytest.fixture
def stub_client():
    return LLMClient(stub=True, cache_dir=None)


@pytest.fixture
def sensitivity_context():
    from agent.mrp import load_sensitivity_context
    return load_sensitivity_context(EXAMPLES_DIR / "sensitivity_report_wuxi.json")


@pytest.fixture
def sample_signal():
    return Signal(
        id="test_signal_001",
        source_type=SignalSourceType.FILE,
        source_name="Test Source",
        source_url="https://example.com/test",
        collected_at="2026-05-15T10:00:00+00:00",
        raw_content="US announces 55% tariff on Chinese pharmaceutical starting materials...",
        raw_content_hash="abc123",
    )


@pytest.fixture
def tmp_state_file(tmp_path):
    return tmp_path / "test_state.json"
