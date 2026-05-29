import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 1000

USE_STUB = os.getenv("USE_STUB", "true").lower() == "true"

DATA_DIR = "data"
SCHEMAS_DIR = f"{DATA_DIR}/schemas"
TWINS_DIR = f"{DATA_DIR}/twins"
GROUND_TRUTH_DIR = f"{DATA_DIR}/ground_truth"
