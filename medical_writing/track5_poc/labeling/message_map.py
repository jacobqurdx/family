"""
MessageMapManager: persist and reload message maps (JSON under MESSAGE_MAPS_DIR).

The locked message map is the alignment milestone of Track 5 — the input that a
later CCDS authoring step (Track 1/2) consumes.
"""
import json
from pathlib import Path
from typing import Optional

from labeling.labeling_models import MessageMap
import config


class MessageMapManager:
    def __init__(self, maps_dir: Optional[str] = None):
        self._dir = Path(maps_dir or config.MESSAGE_MAPS_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, message_map: MessageMap) -> None:
        path = self._dir / f"{message_map.map_id}.json"
        path.write_text(message_map.model_dump_json(indent=2))

    def load(self, map_id: str) -> MessageMap:
        path = self._dir / f"{map_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Message map not found: {map_id}")
        return MessageMap(**json.loads(path.read_text()))

    def list_ids(self) -> list:
        return sorted(f.stem for f in self._dir.glob("*.json"))
