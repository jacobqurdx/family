"""
OutputSimulator: loads pre-simulated AI outputs for sections.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

from workflow.models import SimulatedOutput
import config


class OutputSimulator:
    def __init__(self, mode: Optional[str] = None):
        self._mode = mode or config.SIMULATION_MODE

    def load_section(self, section_id: str, mode: Optional[str] = None) -> SimulatedOutput:
        tier = mode or self._mode
        path = Path(config.SIMULATED_DIR) / tier / f"{section_id}.json"
        if not path.exists():
            raise FileNotFoundError(
                f"Simulated output not found: {tier}/{section_id}.json"
            )
        raw = json.loads(path.read_text())
        return SimulatedOutput(**raw)

    def section_exists(self, section_id: str, mode: Optional[str] = None) -> bool:
        tier = mode or self._mode
        path = Path(config.SIMULATED_DIR) / tier / f"{section_id}.json"
        return path.exists()

    @property
    def mode(self) -> str:
        return self._mode
