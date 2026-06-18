#!/usr/bin/env bash
# stop_cloud.sh — Stop Kitty cloud processes
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${REPO}/logs"

stop_pid() {
  local name="$1" pid_file="${LOG_DIR}/${2}.pid"
  if [[ -f "${pid_file}" ]]; then
    local pid
    pid=$(cat "${pid_file}")
    if kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" && echo "  ${name}: stopped (pid ${pid})"
    else
      echo "  ${name}: not running"
    fi
    rm -f "${pid_file}"
  else
    echo "  ${name}: no pid file"
  fi
}

echo "Stopping Kitty..."
stop_pid "gateway" "gateway"
stop_pid "ui" "nextjs"

# Fallback: kill by port
kill "$(lsof -ti:8000)" 2>/dev/null && echo "  gateway: killed by port" || true
kill "$(lsof -ti:4000)" 2>/dev/null && echo "  ui: killed by port" || true

echo "Done."
