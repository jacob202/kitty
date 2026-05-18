#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/jacobbrizinski/Projects/kitty"
ENV_FILE="${ROOT_DIR}/kitty_gateway/openwebui.env"
LOG_DIR="${ROOT_DIR}/logs/kitty_gateway"
RUN_DIR="${ROOT_DIR}/kitty_gateway/.run"
OPENWEBUI_VENV="${OPENWEBUI_VENV:-${HOME}/kitty-services/venv}"
JUPYTER_URL="${CODE_EXECUTION_JUPYTER_URL:-http://127.0.0.1:8888}"

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

JUPYTER_URL="${CODE_EXECUTION_JUPYTER_URL:-${JUPYTER_URL}}"
JUPYTER_HOST="$(python3 - <<'PY'
from urllib.parse import urlparse
import os
u = urlparse(os.environ.get("CODE_EXECUTION_JUPYTER_URL","http://127.0.0.1:8888"))
print(u.hostname or "127.0.0.1")
PY
)"
JUPYTER_PORT="$(python3 - <<'PY'
from urllib.parse import urlparse
import os
u = urlparse(os.environ.get("CODE_EXECUTION_JUPYTER_URL","http://127.0.0.1:8888"))
print(u.port or 8888)
PY
)"

TOKEN="$(python3 - <<'PY'
import os
print(os.environ.get("CODE_EXECUTION_JUPYTER_AUTH_TOKEN",""))
PY
)"

if [[ -z "${TOKEN}" ]]; then
  echo "Missing CODE_EXECUTION_JUPYTER_AUTH_TOKEN in ${ENV_FILE}"
  exit 1
fi

if pgrep -f "jupyter-lab.*--ip=${JUPYTER_HOST}.*--port=${JUPYTER_PORT}" >/dev/null 2>&1; then
  echo "Jupyter already running on ${JUPYTER_HOST}:${JUPYTER_PORT}"
  exit 0
fi

nohup "${OPENWEBUI_VENV}/bin/jupyter" lab \
  --no-browser \
  --ip="${JUPYTER_HOST}" \
  --port="${JUPYTER_PORT}" \
  --IdentityProvider.token="${TOKEN}" \
  --ServerApp.password='' \
  > "${LOG_DIR}/jupyter.log" 2>&1 < /dev/null &

echo $! > "${RUN_DIR}/jupyter.pid"
sleep 2
echo "Jupyter launch requested. Check: ${LOG_DIR}/jupyter.log"
