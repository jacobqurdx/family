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
RESULTS_DIR          = f"{DATA_DIR}/results"

# ── Aliases for SHARED core modules ───────────────────────────────────────────
# core/twin.py and core/schema.py were copied from Track 1 unchanged and refer to
# config.TWINS_DIR / config.SCHEMAS_DIR. In Track 3 the content twin IS the
# Track 1 twin, so TWINS_DIR points at the content twin store.
TWINS_DIR   = CONTENT_TWINS_DIR
SCHEMAS_DIR = f"{DATA_DIR}/schemas"

for d in [RESULTS_DIR, SCHEMAS_DIR]:
    Path(d).mkdir(parents=True, exist_ok=True)

# Role for this session — set by operator at startup
# Simulates permission model without authentication
SESSION_ROLE = os.getenv("SESSION_ROLE", "regulatory_affairs")
# Valid values: regulatory_affairs | medical_writing | clinical_science |
#               clinical_operations | biostatistician | qc_compliance | admin
