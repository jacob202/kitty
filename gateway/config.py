
import os
from pathlib import Path
from dotenv import load_dotenv

# Load all environment files
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# 1. Gateway Settings
GATEWAY_HOST = os.environ.get("GATEWAY_HOST", "127.0.0.1")
GATEWAY_PORT = int(os.environ.get("GATEWAY_PORT", "5001"))
GATEWAY_BASE_URL = f"http://{GATEWAY_HOST}:{GATEWAY_PORT}"

# 2. LiteLLM Proxy Settings
LITELLM_HOST = os.environ.get("LITELLM_HOST", "127.0.0.1")
LITELLM_PORT = int(os.environ.get("LITELLM_PORT", "8001"))
LITELLM_BASE_URL = f"http://{LITELLM_HOST}:{LITELLM_PORT}"

# 3. Canonical Paths
CANONICAL_LIBRARY_DIR = Path("/Volumes/DATA/books_canonical_v2")
STATUS_DB_PATH = PROJECT_ROOT / "data/curation_status.db"
