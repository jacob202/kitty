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

"${PYTHON_BIN}" - <<'PY'
import sys
import requests
import os

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

ok = 0
skipped = 0
failed = 0

for url in function_urls:
    try:
        rr = s.post(f"{base}/api/v1/functions/load/url", json={"url": url}, timeout=45)
    except Exception as e:
        print(f"FAIL {url} -> {e}")
        failed += 1
        continue

    if rr.status_code < 300:
        print(f"OK   {url}")
        ok += 1
        continue

    body = (rr.text or "")[:400].lower()
    if rr.status_code in (400, 409) and ("already" in body or "exists" in body):
        print(f"SKIP {url} (already present)")
        skipped += 1
        continue

    print(f"FAIL {url} -> {rr.status_code} {rr.text[:300]}")
    failed += 1

print(f"Function import summary: ok={ok} skipped={skipped} failed={failed}")
if failed > 0:
    sys.exit(1)
PY
