import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402


@pytest.fixture(autouse=True)
def _default_sim_mode():
    config.SIMULATION_MODE = "high_quality"
    yield
    config.SIMULATION_MODE = "high_quality"


@pytest.fixture
def tmp_results(tmp_path, monkeypatch):
    """Redirect session persistence to a temp dir."""
    monkeypatch.setattr(config, "RESULTS_DIR", str(tmp_path / "results"))
    monkeypatch.setattr(config, "MESSAGE_MAPS_DIR", str(tmp_path / "message_maps"))
    return tmp_path
