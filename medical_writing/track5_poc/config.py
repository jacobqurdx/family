import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4000

USE_STUB = os.getenv("USE_STUB", "true").lower() == "true"
SIMULATION_MODE = os.getenv("SIMULATION_MODE", "high_quality")

DATA_DIR = "data"
CI_TWINS_DIR         = f"{DATA_DIR}/ci_twins"
CONTENT_TWINS_DIR    = f"{DATA_DIR}/content_twins"
STRUCTURE_TWINS_DIR  = f"{DATA_DIR}/structure_twins"
CHECKLISTS_DIR       = f"{DATA_DIR}/checklists"
MESSAGE_MAPS_DIR     = f"{DATA_DIR}/message_maps"
RESULTS_DIR          = f"{DATA_DIR}/results"

SESSION_ROLE = os.getenv("SESSION_ROLE", "regulatory_affairs")

# ── Aliases for SHARED Track 1/3 core modules ────────────────────────────────
# core/twin.py refers to config.TWINS_DIR; core/schema.py to config.SCHEMAS_DIR.
TWINS_DIR            = CONTENT_TWINS_DIR
SCHEMAS_DIR          = f"{DATA_DIR}/schemas"
# regulatory.framework_twin refers to this if ever instantiated.
FRAMEWORK_TWINS_DIR  = "../track3_poc/data/framework_twins"

for d in [MESSAGE_MAPS_DIR, RESULTS_DIR, SCHEMAS_DIR]:
    Path(d).mkdir(parents=True, exist_ok=True)
