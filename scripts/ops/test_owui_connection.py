
import requests
import os
from pathlib import Path
from dotenv import load_dotenv
import json

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / "kitty_gateway/openwebui.env")
URL = os.environ.get("WEBUI_URL", "http://127.0.0.1:3001")
EMAIL = os.environ.get("WEBUI_ADMIN_EMAIL")
PW = os.environ.get("WEBUI_ADMIN_PASSWORD")

print(f"Testing connection to: {URL}")
try:
    resp = requests.post(f"{URL}/api/v1/auths/signin", json={"email": EMAIL, "password": PW}, timeout=10)
    token = resp.json().get("token")
    
    k_resp = requests.get(f"{URL}/api/v1/knowledge/", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    data = k_resp.json()
    print(f"DEBUG RAW KB DATA: {json.dumps(data, indent=2)[:500]}")

except Exception as e:
    print(f"Connection Failed: {e}")
