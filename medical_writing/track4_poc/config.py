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
CONTENT_TWINS_DIR    = f"{DATA_DIR}/content_twins"
STRUCTURE_TWINS_DIR  = f"{DATA_DIR}/structure_twins"
FRAMEWORK_TWINS_DIR  = f"{DATA_DIR}/framework_twins"
GUIDANCE_DOCS_DIR    = f"{DATA_DIR}/guidance_docs"
GROUND_TRUTH_DIR     = f"{DATA_DIR}/ground_truth"
CHECKLISTS_DIR       = f"{DATA_DIR}/checklists"
SESSIONS_DIR         = f"{DATA_DIR}/sessions"
HANDOFFS_DIR         = f"{DATA_DIR}/handoffs"
RESULTS_DIR          = f"{DATA_DIR}/results"

# ── Aliases for SHARED Track 1/3 core modules ────────────────────────────────
# core/twin.py and core/schema.py refer to config.TWINS_DIR / config.SCHEMAS_DIR.
TWINS_DIR   = CONTENT_TWINS_DIR
SCHEMAS_DIR = f"{DATA_DIR}/schemas"

for d in [SESSIONS_DIR, HANDOFFS_DIR, RESULTS_DIR, SCHEMAS_DIR]:
    Path(d).mkdir(parents=True, exist_ok=True)

# Role for this session — set by operator at startup (simulated permissions)
SESSION_ROLE = os.getenv("SESSION_ROLE", "regulatory_affairs")
