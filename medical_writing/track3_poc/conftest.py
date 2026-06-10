import sys
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402


@pytest.fixture(autouse=True)
def _default_sim_mode():
    """Reset simulation mode to high_quality before every test."""
    config.SIMULATION_MODE = "high_quality"
    yield
    config.SIMULATION_MODE = "high_quality"


@pytest.fixture
def tmp_twins(tmp_path, monkeypatch):
    """
    Copy the content twins into a temp dir and point config at it, so tests that
    back-propagate values do not mutate the real demo data files.
    Returns the temp content-twins directory path.
    """
    src = ROOT / "data" / "content_twins"
    dst = tmp_path / "content_twins"
    shutil.copytree(src, dst)
    monkeypatch.setattr(config, "CONTENT_TWINS_DIR", str(dst))
    monkeypatch.setattr(config, "TWINS_DIR", str(dst))
    return dst
