#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/jacobbrizinski/Projects/kitty"
RUN_DIR="${ROOT_DIR}/kitty_gateway/.run"

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

stop_service() {
  local name="$1"
  local pid_file="${RUN_DIR}/${name}.pid"
  local pattern
  pattern="$(service_pattern "${name}")"

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
stop_service "openwebui"
stop_service "litellm"
stop_service "gateway"
stop_service "jupyter"
stop_service "openterminal"
stop_service "tool-filesystem"
stop_service "tool-memory"
stop_service "tool-time"
stop_service "tool-weather"
stop_service "mlx"
