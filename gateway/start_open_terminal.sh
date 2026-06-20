#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/kitty_gateway/openwebui.env"
LOG_DIR="${ROOT_DIR}/logs/kitty_gateway"
RUN_DIR="${ROOT_DIR}/kitty_gateway/.run"
OPENWEBUI_VENV="${OPENWEBUI_VENV:-${HOME}/kitty-services/venv}"
OPEN_TERMINAL_URL="${OPEN_TERMINAL_URL:-http://127.0.0.1:9614}"

mkdir -p "${LOG_DIR}" "${RUN_DIR}"
cd "${ROOT_DIR}"

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

source "${OPENWEBUI_VENV}/bin/activate"

HOST="$(python3 - <<'PY'
from urllib.parse import urlparse
import os
u = urlparse(os.environ.get("OPEN_TERMINAL_URL","http://127.0.0.1:9614"))
print(u.hostname or "127.0.0.1")
PY
)"
PORT="$(python3 - <<'PY'
from urllib.parse import urlparse
import os
u = urlparse(os.environ.get("OPEN_TERMINAL_URL","http://127.0.0.1:9614"))
print(u.port or 9614)
PY
)"

if [[ -z "${OPEN_TERMINAL_API_KEY:-}" ]]; then
  echo "Missing OPEN_TERMINAL_API_KEY in ${ENV_FILE}"
  exit 1
fi

if pgrep -f "open-terminal run .*--host ${HOST} .*--port ${PORT}" >/dev/null 2>&1; then
  echo "Open Terminal already running on ${HOST}:${PORT}"
  exit 0
fi

nohup "${OPENWEBUI_VENV}/bin/open-terminal" run \
  --host "${HOST}" \
  --port "${PORT}" \
  --api-key "${OPEN_TERMINAL_API_KEY}" \
  > "${LOG_DIR}/open-terminal.log" 2>&1 < /dev/null &

echo $! > "${RUN_DIR}/open-terminal.pid"
sleep 2
echo "Open Terminal launch requested on ${HOST}:${PORT}. Check: ${LOG_DIR}/open-terminal.log"
