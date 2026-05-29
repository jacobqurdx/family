"""
IngestionSessionManager: create, load, save, and list ingestion sessions.

Persistence is dual-mode:
  - Local dev:  JSON files under SESSIONS_DIR/ingestion/
  - Snowflake SiS:  INGESTION_SESSIONS table (VARIANT column)
"""
from __future__ import annotations
import json
import uuid
import datetime
from pathlib import Path
from typing import List, Optional

from ingestion.verification import IngestionSession
import config


class IngestionSessionManager:
    def __init__(self, sessions_dir: Optional[str] = None):
        self._dir = Path(sessions_dir or f"{config.SESSIONS_DIR}/ingestion")
        if not config.IS_SNOWFLAKE:
            self._dir.mkdir(parents=True, exist_ok=True)

    # ── Public API ────────────────────────────────────────────────────────────

    def create(
        self,
        document_path: str,
        twin_id: str,
        schema_id: str,
        writer_id: str,
    ) -> IngestionSession:
        session_id = str(uuid.uuid4())[:8]
        doc_path = Path(document_path)
        session = IngestionSession(
            session_id=session_id,
            document_filename=doc_path.name,
            document_path=str(doc_path),
            twin_id=twin_id,
            schema_id=schema_id,
            writer_id=writer_id,
            started_at=datetime.datetime.utcnow(),
        )
        self.save(session)
        return session

    def save(self, session: IngestionSession) -> None:
        if config.IS_SNOWFLAKE:
            self._sf_save(session)
        else:
            path = self._dir / f"{session.session_id}.json"
            data = session.model_dump(mode="json")
            path.write_text(json.dumps(data, indent=2, default=str))

    def load(self, session_id: str) -> IngestionSession:
        if config.IS_SNOWFLAKE:
            return self._sf_load(session_id)
        path = self._dir / f"{session_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")
        raw = json.loads(path.read_text())
        raw["extraction_results"] = _normalize_int_keys(raw.get("extraction_results", {}))
        raw["verification_records"] = _normalize_int_keys(raw.get("verification_records", {}))
        return IngestionSession(**raw)

    def list_sessions(self) -> List[IngestionSession]:
        if config.IS_SNOWFLAKE:
            return self._sf_list()
        sessions = []
        for f in sorted(self._dir.glob("*.json")):
            try:
                sessions.append(self.load(f.stem))
            except Exception:
                pass
        return sessions

    def get_session_summary(self, session: IngestionSession) -> dict:
        return {
            "session_id": session.session_id,
            "document": session.document_filename,
            "twin_id": session.twin_id,
            "writer_id": session.writer_id,
            "status": session.status,
            "current_layer": session.current_layer,
            "total_layers": session.total_layers,
            "confirmed": session.total_nodes_confirmed,
            "corrected": session.total_nodes_corrected,
            "overridden": session.total_nodes_overridden,
            "missing": session.total_nodes_missing,
            "started_at": str(session.started_at),
        }

    # ── Snowflake persistence (SiS only) ──────────────────────────────────────

    @staticmethod
    def _sf_table() -> str:
        """Fully-qualified table name using the active Snowpark session's database."""
        from snowflake.snowpark.context import get_active_session
        sf = get_active_session()
        db = sf.get_current_database().strip('"')
        schema = sf.get_current_schema().strip('"')
        return f"{db}.{schema}.INGESTION_SESSIONS"

    def _sf_save(self, session: IngestionSession) -> None:
        from snowflake.snowpark.context import get_active_session
        sf = get_active_session()
        table = self._sf_table()
        data = session.model_dump(mode="json")
        # Single-quote escape for Snowflake SQL string literal
        json_str = json.dumps(data, default=str).replace("'", "''")
        sf.sql(f"""
            MERGE INTO {table} AS t
            USING (
                SELECT '{session.session_id}' AS id,
                       PARSE_JSON('{json_str}')  AS d
            ) AS s ON t.session_id = s.id
            WHEN MATCHED THEN
                UPDATE SET t.data = s.d, t.updated_at = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN
                INSERT (session_id, data, updated_at)
                VALUES (s.id, s.d, CURRENT_TIMESTAMP())
        """).collect()

    def _sf_load(self, session_id: str) -> IngestionSession:
        from snowflake.snowpark.context import get_active_session
        sf = get_active_session()
        table = self._sf_table()
        rows = sf.sql(
            f"SELECT data::VARCHAR AS d FROM {table} WHERE session_id = '{session_id}'"
        ).collect()
        if not rows:
            raise FileNotFoundError(f"Session not found: {session_id}")
        raw = json.loads(rows[0]["D"])
        raw["extraction_results"] = _normalize_int_keys(raw.get("extraction_results", {}))
        raw["verification_records"] = _normalize_int_keys(raw.get("verification_records", {}))
        return IngestionSession(**raw)

    def _sf_list(self) -> List[IngestionSession]:
        from snowflake.snowpark.context import get_active_session
        sf = get_active_session()
        table = self._sf_table()
        rows = sf.sql(
            f"SELECT session_id FROM {table} ORDER BY updated_at DESC"
        ).collect()
        sessions = []
        for row in rows:
            try:
                sessions.append(self._sf_load(row["SESSION_ID"]))
            except Exception:
                pass
        return sessions


def _normalize_int_keys(d: dict) -> dict:
    """Convert string integer keys back to ints after JSON round-trip."""
    result = {}
    for k, v in d.items():
        try:
            result[int(k)] = v
        except (ValueError, TypeError):
            result[k] = v
    return result
