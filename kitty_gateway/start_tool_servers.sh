#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/jacobbrizinski/Projects/kitty"
RUN_DIR="${ROOT_DIR}/kitty_gateway/.run"
LOG_DIR="${ROOT_DIR}/logs/kitty_gateway"
ENV_FILE="${ROOT_DIR}/kitty_gateway/openwebui.env"
OPENAPI_ROOT="${ROOT_DIR}/kitty_gateway/openapi-servers/servers"
OPENWEBUI_VENV_DEFAULT="${HOME}/kitty-services/venv"
source "${ROOT_DIR}/kitty_gateway/lib/load_env_safe.sh"

mkdir -p "${RUN_DIR}" "${LOG_DIR}"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  load_env_assignments "${ROOT_DIR}/.env"
fi

if [[ -f "${ENV_FILE}" ]]; then
  load_env_assignments "${ENV_FILE}"
fi

OPENWEBUI_VENV="${OPENWEBUI_VENV:-${OPENWEBUI_VENV_DEFAULT}}"
PYTHON_BIN="${OPENWEBUI_VENV}/bin/python"
PIP_BIN="${OPENWEBUI_VENV}/bin/pip"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Python not found: ${PYTHON_BIN}"
  exit 1
fi
if [[ ! -x "${PIP_BIN}" ]]; then
  echo "pip not found: ${PIP_BIN}"
  exit 1
fi

if [[ ! -d "${OPENAPI_ROOT}" ]]; then
  echo "OpenAPI community servers not found at ${OPENAPI_ROOT}"
  echo "Clone: git clone https://github.com/open-webui/openapi-servers kitty_gateway/openapi-servers"
  exit 1
fi

ensure_deps() {
  if "${PYTHON_BIN}" - <<'PY' >/dev/null 2>&1
import fastapi
import uvicorn
import pytz
import dateutil
import requests
PY
  then
    return 0
  fi

  echo "Installing base community server dependencies..."
  "${PIP_BIN}" install -q fastapi "uvicorn[standard]" pydantic python-multipart pytz python-dateutil requests
}

start_one() {
  local name="$1"
  local subdir="$2"
  local port="$3"
  local extra_env="${4:-}"
  local pattern="uvicorn main:app --host 127.0.0.1 --port ${port}"
  local pid_file="${RUN_DIR}/${name}.pid"
  local log_file="${LOG_DIR}/${name}.log"

  if pgrep -f "${pattern}" >/dev/null 2>&1; then
    local pid
    pid="$(pgrep -f "${pattern}" | head -n1)"
    echo "${name}: already running (pid ${pid})"
    echo "${pid}" > "${pid_file}"
    return 0
  fi

  echo "Starting ${name}..."
  nohup bash -lc "cd '${OPENAPI_ROOT}/${subdir}' && ${extra_env} '${PYTHON_BIN}' -m uvicorn main:app --host 127.0.0.1 --port ${port}" >"${log_file}" 2>&1 &
  local launcher_pid=$!
  echo "${launcher_pid}" > "${pid_file}"
  sleep 1

  if pgrep -f "${pattern}" >/dev/null 2>&1; then
    local pid
    pid="$(pgrep -f "${pattern}" | head -n1)"
    echo "${pid}" > "${pid_file}"
    echo "${name}: started (pid ${pid})"
  else
    echo "${name}: failed to start. See ${log_file}"
    return 1
  fi
}

ensure_deps

# Restrict filesystem server to explicit safe roots.
FS_ALLOWED="${FS_ALLOWED_DIRECTORIES:-${ROOT_DIR},${HOME}/Desktop,${HOME}/Documents,${HOME}/Downloads}"
MEMORY_FILE_PATH="${MEMORY_FILE_PATH:-${ROOT_DIR}/data/openwebui/community_memory.jsonl}"
mkdir -p "$(dirname "${MEMORY_FILE_PATH}")"

start_one "tool-filesystem" "filesystem" "9721" "ALLOWED_DIRECTORIES='${FS_ALLOWED}'"
start_one "tool-memory" "memory" "9722" "MEMORY_FILE_PATH='${MEMORY_FILE_PATH}'"
start_one "tool-time" "time" "9723" ""
start_one "tool-weather" "weather" "9724" ""

echo "Community tool servers launch requested."
