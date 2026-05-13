#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/jacobbrizinski/Projects/kitty"
RUN_DIR="${ROOT_DIR}/kitty_gateway/.run"
source "${ROOT_DIR}/kitty_gateway/lib/load_env_safe.sh"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  load_env_assignments "${ROOT_DIR}/.env"
fi
if [[ -f "${ROOT_DIR}/kitty_gateway/openwebui.env" ]]; then
  load_env_assignments "${ROOT_DIR}/kitty_gateway/openwebui.env"
fi

OPENWEBUI_PORT="${OPENWEBUI_PORT:-3000}"
OPENWEBUI_HEALTH_URL="$(echo "${WEBUI_URL:-http://127.0.0.1:${OPENWEBUI_PORT}}" | sed 's!/*$!!')/health"

service_pattern() {
  local name="$1"
  case "${name}" in
    mlx) echo "mlx_lm.server" ;;
    litellm) echo "venv-litellm/bin/litellm --config kitty_gateway/litellm_config.yaml" ;;
    gateway) echo "venv/bin/uvicorn gateway.app:app --host 127.0.0.1 --port 8000" ;;
    openwebui) echo "venv/bin/open-webui serve" ;;
    jupyter) echo "venv/bin/jupyter.*lab.*--ip=127.0.0.1.*--port=8888" ;;
    cloudflare) echo "cloudflared tunnel" ;;
    openterminal) echo "venv/bin/open-terminal run --host 127.0.0.1 --port" ;;
    tool-filesystem) echo "uvicorn main:app --host 127.0.0.1 --port 9721" ;;
    tool-memory) echo "uvicorn main:app --host 127.0.0.1 --port 9722" ;;
    tool-time) echo "uvicorn main:app --host 127.0.0.1 --port 9723" ;;
    tool-weather) echo "uvicorn main:app --host 127.0.0.1 --port 9724" ;;
    *) echo "" ;;
  esac
}

check_pid() {
  local name="$1"
  local pid_file="${RUN_DIR}/${name}.pid"
  local pattern
  pattern="$(service_pattern "${name}")"
  if pgrep -f "${pattern}" >/dev/null 2>&1; then
    local pid
    pid="$(pgrep -f "${pattern}" | head -n1)"
    echo "${name}: running (pid ${pid})"
    echo "${pid}" > "${pid_file}"
  else
    echo "${name}: stopped"
    rm -f "${pid_file}"
  fi
}

check_http() {
  local name="$1"
  local url="$2"
  local auth_header="${3:-}"
  local max_time="${4:-2}"
  local ok_status=0
  if [[ -n "${auth_header}" ]]; then
    if curl -fsS --max-time "${max_time}" -H "${auth_header}" "${url}" >/dev/null 2>&1; then
      echo "${name} endpoint: healthy (${url})"
      ok_status=1
    fi
  elif curl -fsS --max-time "${max_time}" "${url}" >/dev/null 2>&1; then
    echo "${name} endpoint: healthy (${url})"
    ok_status=1
  fi

  if [[ "${ok_status}" != "1" ]]; then
    echo "${name} endpoint: unavailable (${url})"
  fi
}

check_pid "mlx"
check_pid "litellm"
check_pid "gateway"
check_pid "openwebui"
check_pid "jupyter"
check_pid "openterminal"
check_pid "tool-filesystem"
check_pid "tool-memory"
check_pid "tool-time"
check_pid "tool-weather"
check_pid "cloudflare"
echo
check_http "litellm" "http://127.0.0.1:8001/health" "Authorization: Bearer ${LITELLM_MASTER_KEY:-kitty-local-key-change-me}" 8
check_http "gateway" "http://127.0.0.1:8000/health"
check_http "openwebui" "${OPENWEBUI_HEALTH_URL}"
check_http "jupyter" "http://127.0.0.1:8888/api" "Authorization: token ${CODE_EXECUTION_JUPYTER_AUTH_TOKEN:-}"
check_http "openterminal" "${OPEN_TERMINAL_URL:-http://127.0.0.1:9614}/health"
check_http "tool-filesystem" "http://127.0.0.1:9721/openapi.json"
check_http "tool-memory" "http://127.0.0.1:9722/openapi.json"
check_http "tool-time" "http://127.0.0.1:9723/openapi.json"
check_http "tool-weather" "http://127.0.0.1:9724/openapi.json"
