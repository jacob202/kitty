#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/jacobbrizinski/Projects/kitty"
ENV_FILE="${ROOT_DIR}/kitty_gateway/openwebui.env"
DRY_RUN="${DRY_RUN:-0}"

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN="1"
fi
export DRY_RUN

if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing env file: ${ENV_FILE}"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "${ENV_FILE}"
set +a

OPENWEBUI_VENV="${OPENWEBUI_VENV:-${HOME}/kitty-services/venv}"
PYTHON_BIN="${OPENWEBUI_VENV}/bin/python"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Python not found: ${PYTHON_BIN}"
  exit 1
fi

if [[ -z "${WEBUI_URL:-}" || -z "${WEBUI_ADMIN_EMAIL:-}" || -z "${WEBUI_ADMIN_PASSWORD:-}" ]]; then
  echo "Missing WEBUI_URL/WEBUI_ADMIN_EMAIL/WEBUI_ADMIN_PASSWORD in ${ENV_FILE}"
  exit 1
fi

if [[ -z "${TERMINAL_SERVER_CONNECTIONS:-}" ]]; then
  echo "Missing TERMINAL_SERVER_CONNECTIONS in ${ENV_FILE}"
  exit 1
fi

if [[ -z "${TOOL_SERVER_CONNECTIONS:-}" ]]; then
  echo "Missing TOOL_SERVER_CONNECTIONS in ${ENV_FILE}"
  exit 1
fi

"${PYTHON_BIN}" - <<'PY'
import json
import os
import sys

try:
    import requests
except Exception as e:
    print(f"Missing dependency 'requests': {e}")
    sys.exit(1)

webui_url = os.environ["WEBUI_URL"].rstrip("/")
email = os.environ["WEBUI_ADMIN_EMAIL"]
password = os.environ["WEBUI_ADMIN_PASSWORD"]
terminal_raw = os.environ["TERMINAL_SERVER_CONNECTIONS"]
tool_raw = os.environ["TOOL_SERVER_CONNECTIONS"]
dry_run = os.environ.get("DRY_RUN", "0") == "1"

def parse_json(name: str, raw: str):
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"{name} is invalid JSON: {e}")
        sys.exit(1)
    if not isinstance(data, list):
        print(f"{name} must be a JSON list")
        sys.exit(1)
    return data

terminal_servers = parse_json("TERMINAL_SERVER_CONNECTIONS", terminal_raw)
tool_servers = parse_json("TOOL_SERVER_CONNECTIONS", tool_raw)

if dry_run:
    print("Dry run mode: no API calls made.")
    print("Target:", webui_url)
    print("TERMINAL_SERVER_CONNECTIONS:")
    print(json.dumps(terminal_servers, indent=2))
    print("TOOL_SERVER_CONNECTIONS:")
    print(json.dumps(tool_servers, indent=2))
    sys.exit(0)

s = requests.Session()
signin_url = f"{webui_url}/api/v1/auths/signin"
r = s.post(signin_url, json={"email": email, "password": password}, timeout=15)
if r.status_code >= 400:
    print(f"Signin failed: {r.status_code} {r.text[:300]}")
    sys.exit(1)

try:
    signin_payload = r.json()
except Exception:
    signin_payload = {}

token = signin_payload.get("token")
if token:
    s.headers.update({"Authorization": f"Bearer {token}"})

term_url = f"{webui_url}/api/v1/configs/terminal_servers"
tool_url = f"{webui_url}/api/v1/configs/tool_servers"

r_term = s.post(term_url, json={"TERMINAL_SERVER_CONNECTIONS": terminal_servers}, timeout=20)
if r_term.status_code >= 400:
    print(f"Terminal sync failed: {r_term.status_code} {r_term.text[:300]}")
    sys.exit(1)

r_tool = s.post(tool_url, json={"TOOL_SERVER_CONNECTIONS": tool_servers}, timeout=20)
if r_tool.status_code >= 400:
    print(f"Tool sync failed: {r_tool.status_code} {r_tool.text[:300]}")
    sys.exit(1)

print("OpenWebUI integrations synced successfully.")
print(f"- terminal_servers: {len(terminal_servers)}")
print(f"- tool_servers: {len(tool_servers)}")
PY
