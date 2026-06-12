#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${ROOT_DIR}/kitty_gateway/.run"
source "${ROOT_DIR}/gateway/lib/load_env_safe.sh"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  load_env_assignments "${ROOT_DIR}/.env"
fi

GATEWAY_PORT="${GATEWAY_PORT:-5001}"

service_pattern() {
  local name="$1"
  case "${name}" in
    mlx) echo "mlx_lm.server" ;;
    litellm) echo "venv-litellm/bin/litellm --config gateway/litellm_config.yaml" ;;
    gateway) echo "venv/bin/uvicorn gateway.app:app --host 127.0.0.1" ;;
    ui) echo "next dev|next-server|next start" ;;
    cloudflare) echo "cloudflared tunnel" ;;
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
check_pid "ui"
check_pid "cloudflare"
echo
check_http "litellm" "http://127.0.0.1:8001/health" "Authorization: Bearer ${LITELLM_MASTER_KEY:-kitty-local-key-change-me}" 8
check_http "gateway" "http://127.0.0.1:${GATEWAY_PORT}/health"
check_http "ui" "http://127.0.0.1:3000"
