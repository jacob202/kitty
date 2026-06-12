#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${ROOT_DIR}/kitty_gateway/.run"
TMUX_BIN="${TMUX_BIN:-$(command -v tmux || true)}"

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

service_session_name() {
  local name="$1"
  case "${name}" in
    litellm) echo "kitty-litellm" ;;
    gateway) echo "kitty-gateway" ;;
    ui) echo "kitty-ui" ;;
    *) echo "" ;;
  esac
}

stop_service() {
  local name="$1"
  local pid_file="${RUN_DIR}/${name}.pid"
  local pattern
  local session_name
  pattern="$(service_pattern "${name}")"
  session_name="$(service_session_name "${name}")"

  if [[ -n "${TMUX_BIN}" && -n "${session_name}" ]]; then
    "${TMUX_BIN}" kill-session -t "${session_name}" >/dev/null 2>&1 || true
  fi

  if pgrep -f "${pattern}" >/dev/null 2>&1; then
    while read -r pid; do
      [[ -z "${pid}" ]] && continue
      echo "Stopping ${name} (pid ${pid})..."
      kill "${pid}" 2>/dev/null || true
    done < <(pgrep -f "${pattern}")
    sleep 1
    while read -r pid; do
      [[ -z "${pid}" ]] && continue
      kill -9 "${pid}" 2>/dev/null || true
    done < <(pgrep -f "${pattern}")
    echo "${name}: stopped"
    rm -f "${pid_file}"
    return 0
  fi

  if [[ ! -f "${pid_file}" ]]; then
    echo "${name}: no pid file"
    return 0
  fi

  local pid
  pid="$(cat "${pid_file}")"
  if kill -0 "${pid}" 2>/dev/null; then
    echo "Stopping ${name} (pid ${pid})..."
    kill "${pid}" 2>/dev/null || true
    sleep 1
    if kill -0 "${pid}" 2>/dev/null; then
      kill -9 "${pid}" 2>/dev/null || true
    fi
    echo "${name}: stopped"
  else
    echo "${name}: already stopped"
  fi
  rm -f "${pid_file}"
}

stop_service "cloudflare"
stop_service "ui"
stop_service "litellm"
stop_service "gateway"
stop_service "mlx"
