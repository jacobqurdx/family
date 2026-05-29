from __future__ import annotations
import os
from pathlib import Path


def _detect_snowflake() -> bool:
    """Returns True when running inside Streamlit in Snowflake (SiS)."""
    try:
        from snowflake.snowpark.context import get_active_session
        get_active_session()
        return True
    except Exception:
        return False


# True when deployed inside Snowflake SiS; False during local development
IS_SNOWFLAKE: bool = _detect_snowflake()

# Load .env only in local dev (python-dotenv is not needed in SiS)
if not IS_SNOWFLAKE:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4000

DATA_DIR = "data"
SCHEMAS_DIR        = f"{DATA_DIR}/schemas"
TWINS_DIR          = f"{DATA_DIR}/twins"
PROTOCOLS_DIR      = f"{DATA_DIR}/protocols"
ASSIGNMENTS_DIR    = f"{DATA_DIR}/assignments"
SIMULATED_DIR      = f"{DATA_DIR}/simulated_outputs"
SESSIONS_DIR       = f"{DATA_DIR}/sessions"
INGESTION_DIR      = f"{DATA_DIR}/ingestion_results"
RESULTS_DIR        = f"{DATA_DIR}/results"

SIMULATION_MODE = os.getenv("SIMULATION_MODE", "high_quality")

# Only create local directories in dev; SiS uses Snowflake tables instead
if not IS_SNOWFLAKE:
    for d in [SESSIONS_DIR, INGESTION_DIR, RESULTS_DIR,
              f"{SESSIONS_DIR}/ingestion", f"{SESSIONS_DIR}/workflow",
              f"{DATA_DIR}/protocols", f"{DATA_DIR}/assignments",
              f"{SIMULATED_DIR}/high_quality", f"{SIMULATED_DIR}/low_quality"]:
        Path(d).mkdir(parents=True, exist_ok=True)
