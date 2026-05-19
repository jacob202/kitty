
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

def test_real_search():
    print(f"Testing real search at: {URL}")
    try:
        resp = requests.post(f"{URL}/api/v1/auths/signin", json={"email": EMAIL, "password": PW}, timeout=10)
        token = resp.json().get("token")
        
        # 1. Find the ID for 'automotive'
        k_resp = requests.get(f"{URL}/api/v1/knowledge/", headers={"Authorization": f"Bearer {token}"}, timeout=10)
        kbs = k_resp.json().get("items", [])
        kb_id = next((k["id"] for k in kbs if k["name"].lower() == "automotive"), None)
        
        if not kb_id:
            print("KB 'automotive' not found in API list.")
            return

        print(f"Found KB ID: {kb_id}")
        
        # 2. Try the retrieval query
        payload = {
            "collection_names": [kb_id],
            "query": "Ridgeline electrical system",
            "k": 3
        }
        
        r_resp = requests.post(f"{URL}/api/v1/retrieval/query/collection", 
                               headers={"Authorization": f"Bearer {token}"}, 
                               json=payload, timeout=20)
        
        print(f"Search Response ({r_resp.status_code}): {r_resp.text}")

    except Exception as e:
        print(f"Search Test Failed: {e}")

if __name__ == "__main__":
    test_real_search()
