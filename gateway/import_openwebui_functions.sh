#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/jacobbrizinski/Projects/kitty"
ENV_FILE="${ROOT_DIR}/kitty_gateway/openwebui.env"
OPENWEBUI_VENV_DEFAULT="${HOME}/kitty-services/venv"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi
if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ENV_FILE}"
  set +a
fi

OPENWEBUI_VENV="${OPENWEBUI_VENV:-${OPENWEBUI_VENV_DEFAULT}}"
PYTHON_BIN="${OPENWEBUI_VENV}/bin/python"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Python not found: ${PYTHON_BIN}"
  exit 1
fi

if [[ -z "${WEBUI_URL:-}" || -z "${WEBUI_ADMIN_EMAIL:-}" || -z "${WEBUI_ADMIN_PASSWORD:-}" ]]; then
  echo "Missing WEBUI_URL/WEBUI_ADMIN_EMAIL/WEBUI_ADMIN_PASSWORD in ${ENV_FILE}"
  exit 1
fi

export ROOT_DIR

"${PYTHON_BIN}" - <<'PY'
import sys
import requests
import os
import re

base = os.environ["WEBUI_URL"].rstrip("/")
email = os.environ["WEBUI_ADMIN_EMAIL"]
password = os.environ["WEBUI_ADMIN_PASSWORD"]

function_urls = [
    "https://raw.githubusercontent.com/open-webui/functions/main/functions/filters/context_clip/main.py",
    "https://raw.githubusercontent.com/open-webui/functions/main/functions/filters/summarizer/main.py",
    "https://raw.githubusercontent.com/open-webui/functions/main/functions/filters/moderation/main.py",
]

s = requests.Session()
r = s.post(f"{base}/api/v1/auths/signin", json={"email": email, "password": password}, timeout=20)
if r.status_code >= 400:
    print(f"Signin failed: {r.status_code} {r.text[:300]}")
    sys.exit(1)
token = (r.json() or {}).get("token")
if token:
    s.headers.update({"Authorization": f"Bearer {token}"})

def normalize_id(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", name.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        cleaned = "function"
    if cleaned[0].isdigit():
        cleaned = f"f_{cleaned}"
    return cleaned


ROOT_DIR = os.environ.get("ROOT_DIR", "")

local_functions = [
    {
        "path": f"{ROOT_DIR}/gateway/openwebui_filters/kitty_context_injector.py",
        "id": "kitty_context_injector",
        "description": "Injects relevant knowledge, memories, and journal entries into LLM context from Kitty's knowledge base.",
    },
    {
        "path": f"{ROOT_DIR}/gateway/actions/kitty_feeding_schedule.py",
        "id": "kitty_feeding_schedule",
        "description": "Calculate feeding amounts based on metabolic scaling (RER formula) and current weights.",
    },
    {
        "path": f"{ROOT_DIR}/gateway/actions/kitty_audio_measurement.py",
        "id": "kitty_audio_measurement",
        "description": "Quick audio measurement conversions: dB to voltage, voltage divider attenuation, RC filter cutoff frequency.",
    },
    {
        "path": f"{ROOT_DIR}/gateway/actions/kitty_kb_query.py",
        "id": "kitty_kb_query",
        "description": "Quick one-click search of Kitty's knowledge base, memories, and journal.",
    },
]


def import_function(src_label: str, function_id: str, content: str, description: str) -> tuple[str, int]:
    """Create or update a function in OWUI. Returns (status, code)."""
    payload = {
        "id": function_id,
        "name": function_id,
        "content": content,
        "meta": {
            "description": description,
            "manifest": {},
        },
    }

    created = s.post(f"{base}/api/v1/functions/create", json=payload, timeout=45)
    if created.status_code < 300:
        status = "created"
    elif created.status_code in (400, 409) and (
        "taken" in (created.text or "").lower() or "already" in (created.text or "").lower()
    ):
        updated = s.post(f"{base}/api/v1/functions/id/{function_id}/update", json=payload, timeout=45)
        if updated.status_code >= 300:
            print(f"FAIL {src_label} -> update failed ({updated.status_code}) {updated.text[:300]}")
            return ("failed", 1)
        status = "updated"
    else:
        print(f"FAIL {src_label} -> create failed ({created.status_code}) {created.text[:300]}")
        return ("failed", 1)

    current = s.get(f"{base}/api/v1/functions/id/{function_id}", timeout=20)
    if current.status_code < 300:
        state = current.json() if current.content else {}
        if not state.get("is_active", False):
            s.post(f"{base}/api/v1/functions/id/{function_id}/toggle", timeout=20)
        if not state.get("is_global", False):
            s.post(f"{base}/api/v1/functions/id/{function_id}/toggle/global", timeout=20)

    print(f"OK   {src_label} -> {function_id} ({status})")
    return (status, 0)


ok = 0
skipped = 0
failed = 0

# Import remote functions
for url in function_urls:
    try:
        rr = s.post(f"{base}/api/v1/functions/load/url", json={"url": url}, timeout=45)
    except Exception as e:
        print(f"FAIL {url} -> {e}")
        failed += 1
        continue

    if rr.status_code >= 300:
        print(f"FAIL {url} -> {rr.status_code} {rr.text[:300]}")
        failed += 1
        continue

    loaded = rr.json() if rr.content else {}
    name = loaded.get("name", "function")
    content = loaded.get("content", "")
    if not content:
        print(f"FAIL {url} -> no content returned by load/url")
        failed += 1
        continue

    function_id = normalize_id(name)
    result, code = import_function(url, function_id, content, f"Imported from {url}")
    if code == 1:
        failed += 1
    else:
        ok += 1

# Import local functions
for func in local_functions:
    path = func["path"]
    function_id = func["id"]
    description = func["description"]
    if not os.path.isfile(path):
        print(f"FAIL {path} -> file not found")
        failed += 1
        continue
    with open(path, "r") as fh:
        content = fh.read()
    if not content:
        print(f"FAIL {path} -> empty file")
        failed += 1
        continue
    result, code = import_function(path, function_id, content, description)
    if code == 1:
        failed += 1
    else:
        ok += 1

print(f"Function import summary: ok={ok} skipped={skipped} failed={failed}")
if failed > 0:
    sys.exit(1)
PY
