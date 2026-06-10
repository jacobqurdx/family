import sys
import shutil
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
def tmp_dirs(tmp_path, monkeypatch):
    """
    Point session/handoff/content-twin storage at temp dirs so tests don't
    mutate shared Track 3 demo data or accumulate runtime files.
    """
    twins_src = ROOT / "data" / "content_twins"
    twins_dst = tmp_path / "content_twins"
    shutil.copytree(twins_src, twins_dst)
    monkeypatch.setattr(config, "CONTENT_TWINS_DIR", str(twins_dst))
    monkeypatch.setattr(config, "TWINS_DIR", str(twins_dst))
    monkeypatch.setattr(config, "SESSIONS_DIR", str(tmp_path / "sessions"))
    monkeypatch.setattr(config, "HANDOFFS_DIR", str(tmp_path / "handoffs"))
    return tmp_path
