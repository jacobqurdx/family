"""
DigitalTwin: the authoritative structured representation of a trial.
Wraps a DigitalTwinRecord and provides query, update, and diff operations.

Persistence is dual-mode:
  - Local dev:  JSON file under TWINS_DIR/
  - Snowflake SiS:  DIGITAL_TWINS table (VARIANT column)
"""
from __future__ import annotations
from pathlib import Path
import json
import datetime
from core.models import DigitalTwinRecord, TwinElement, ElementStatus
import config


class DigitalTwin:
    def __init__(self, record: DigitalTwinRecord):
        self._record = record

    # ── Persistence ───────────────────────────────────────────────────────────

    @classmethod
    def load(cls, twin_id: str) -> "DigitalTwin":
        if config.IS_SNOWFLAKE:
            return cls._sf_load(twin_id)
        path = Path(config.TWINS_DIR) / f"{twin_id}.json"
        raw = json.loads(path.read_text())
        return cls(DigitalTwinRecord(**raw))

    @classmethod
    def new(cls, twin_id: str, schema_id: str, trial_name: str) -> "DigitalTwin":
        record = DigitalTwinRecord(twin_id=twin_id, schema_id=schema_id, trial_name=trial_name)
        return cls(record)

    def save(self) -> None:
        if config.IS_SNOWFLAKE:
            self._sf_save()
            return
        path = Path(config.TWINS_DIR) / f"{self._record.twin_id}.json"
        path.write_text(self._record.model_dump_json(indent=2))

    # ── Snowflake persistence (SiS only) ──────────────────────────────────────

    @staticmethod
    def _sf_table() -> str:
        from snowflake.snowpark.context import get_active_session
        sf = get_active_session()
        db = sf.get_current_database().strip('"')
        schema = sf.get_current_schema().strip('"')
        return f"{db}.{schema}.DIGITAL_TWINS"

    @classmethod
    def _sf_load(cls, twin_id: str) -> "DigitalTwin":
        from snowflake.snowpark.context import get_active_session
        sf = get_active_session()
        table = cls._sf_table()
        rows = sf.sql(
            f"SELECT data::VARCHAR AS d FROM {table} WHERE twin_id = '{twin_id}'"
        ).collect()
        if not rows:
            raise FileNotFoundError(f"Twin not found: {twin_id}")
        raw = json.loads(rows[0]["D"])
        return cls(DigitalTwinRecord(**raw))

    def _sf_save(self) -> None:
        from snowflake.snowpark.context import get_active_session
        sf = get_active_session()
        table = self._sf_table()
        # Single-quote escape for Snowflake SQL string literal
        json_str = self._record.model_dump_json().replace("'", "''")
        sf.sql(f"""
            MERGE INTO {table} AS t
            USING (
                SELECT '{self._record.twin_id}' AS id,
                       PARSE_JSON('{json_str}')  AS d
            ) AS s ON t.twin_id = s.id
            WHEN MATCHED THEN
                UPDATE SET t.data = s.d, t.updated_at = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN
                INSERT (twin_id, data, updated_at)
                VALUES (s.id, s.d, CURRENT_TIMESTAMP())
        """).collect()

    # ── Query / update API ────────────────────────────────────────────────────

    @property
    def schema_id(self) -> str:
        return self._record.schema_id

    @property
    def trial_name(self) -> str:
        return self._record.trial_name

    @property
    def twin_id(self) -> str:
        return self._record.twin_id

    def get(self, element_id: str):
        return self._record.elements.get(element_id)

    def get_value(self, element_id: str):
        el = self.get(element_id)
        return el.value if el else None

    def set(self, element_id: str, value, source: str = "user",
            status: ElementStatus = ElementStatus.VERIFIED,
            modified_by: str = "user"):
        el = TwinElement(
            element_id=element_id,
            value=value,
            status=status,
            source=source,
            last_modified=datetime.datetime.utcnow(),
            modified_by=modified_by
        )
        self._record.elements[element_id] = el

    def set_inferred(self, element_id: str, value, source_element: str):
        el = TwinElement(
            element_id=element_id,
            value=value,
            status=ElementStatus.INFERRED,
            source=f"inferred_from:{source_element}",
            last_modified=datetime.datetime.utcnow(),
            modified_by="system"
        )
        self._record.elements[element_id] = el

    def override(self, element_id: str, value, justification: str, modified_by: str):
        el = TwinElement(
            element_id=element_id,
            value=value,
            status=ElementStatus.OVERRIDDEN,
            source="user_override",
            override_justification=justification,
            last_modified=datetime.datetime.utcnow(),
            modified_by=modified_by
        )
        self._record.elements[element_id] = el

    def get_all(self) -> dict:
        return dict(self._record.elements)

    def get_section_data(self, source_elements: list) -> dict:
        return {
            eid: self.get_value(eid)
            for eid in source_elements
        }

    def diff(self, other: "DigitalTwin") -> list:
        diffs = []
        all_ids = set(self._record.elements.keys()) | set(other._record.elements.keys())
        for eid in all_ids:
            v1 = self.get_value(eid)
            v2 = other.get_value(eid)
            if v1 != v2:
                diffs.append({
                    "element_id": eid,
                    "twin_a": self._record.twin_id,
                    "twin_b": other._record.twin_id,
                    "value_a": v1,
                    "value_b": v2
                })
        return diffs

    def completeness(self, required_elements: list) -> dict:
        total = len(required_elements)
        populated = sum(1 for eid in required_elements if self.get_value(eid) is not None)
        verified = sum(
            1 for eid in required_elements
            if self.get(eid) and self.get(eid).status == ElementStatus.VERIFIED
        )
        return {
            "total": total,
            "populated": populated,
            "verified": verified,
            "completeness_pct": round(populated / total * 100, 1) if total else 0,
            "verification_pct": round(verified / total * 100, 1) if total else 0
        }
