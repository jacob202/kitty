
import os
from pathlib import Path
from dotenv import load_dotenv

# Load all environment files
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / "kitty_gateway/openwebui.env")

# 1. Gateway Settings
GATEWAY_HOST = os.environ.get("GATEWAY_HOST", "127.0.0.1")
GATEWAY_PORT = int(os.environ.get("GATEWAY_PORT", "8000"))
GATEWAY_BASE_URL = f"http://{GATEWAY_HOST}:{GATEWAY_PORT}"

# 2. LiteLLM Proxy Settings
LITELLM_HOST = os.environ.get("LITELLM_HOST", "127.0.0.1")
LITELLM_PORT = int(os.environ.get("LITELLM_PORT", "8001"))
LITELLM_BASE_URL = f"http://{LITELLM_HOST}:{LITELLM_PORT}"

# 3. OpenWebUI Settings
OWUI_URL = "http://127.0.0.1:3001"

OWUI_ADMIN_EMAIL = os.environ.get("WEBUI_ADMIN_EMAIL")
OWUI_ADMIN_PASSWORD = os.environ.get("WEBUI_ADMIN_PASSWORD")

# 4. Canonical Paths
CANONICAL_LIBRARY_DIR = Path("/Volumes/DATA/books_canonical_v2")
STATUS_DB_PATH = PROJECT_ROOT / "data/curation_status.db"

def get_owui_headers(token: str):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
