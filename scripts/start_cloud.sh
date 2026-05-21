#!/usr/bin/env bash
# start_cloud.sh — Start Kitty in a cloud / remote container environment
# Usage: bash scripts/start_cloud.sh

set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Load .env
if [[ -f "${REPO}/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${REPO}/.env"
  set +a
fi

GW_PORT="${KITTY_GATEWAY_PORT:-5001}"
UI_PORT="${KITTY_UI_PORT:-4000}"
LOG_DIR="${REPO}/logs"
mkdir -p "${LOG_DIR}"

echo "Starting Kitty..."

# ── Gateway ───────────────────────────────────────────────────────────────────
if lsof -ti:"${GW_PORT}" >/dev/null 2>&1; then
  echo "  gateway: already running on :${GW_PORT}"
else
  python3.11 -m uvicorn gateway.app:app \
    --host 0.0.0.0 --port "${GW_PORT}" \
    --log-level warning \
    > "${LOG_DIR}/gateway.log" 2>&1 &
  GW_PID=$!
  echo "${GW_PID}" > "${LOG_DIR}/gateway.pid"

  # Wait until healthy
  for i in $(seq 1 20); do
    sleep 1
    if curl -fs "http://127.0.0.1:${GW_PORT}/health" >/dev/null 2>&1; then
      echo "  gateway: up (pid ${GW_PID}) → http://0.0.0.0:${GW_PORT}"
      break
    fi
    if [[ $i -eq 20 ]]; then
      echo "  gateway: failed to start — check ${LOG_DIR}/gateway.log"
      exit 1
    fi
  done
fi

# ── Next.js UI ────────────────────────────────────────────────────────────────
if lsof -ti:"${UI_PORT}" >/dev/null 2>&1; then
  echo "  ui: already running on :${UI_PORT}"
else
  cd "${REPO}/gateway/kitty-chat"
  npm run dev -- --hostname 0.0.0.0 \
    > "${LOG_DIR}/nextjs.log" 2>&1 &
  NX_PID=$!
  echo "${NX_PID}" > "${LOG_DIR}/nextjs.pid"

  for i in $(seq 1 30); do
    sleep 1
    if curl -fs "http://127.0.0.1:${UI_PORT}" >/dev/null 2>&1; then
      echo "  ui: up (pid ${NX_PID}) → http://0.0.0.0:${UI_PORT}"
      break
    fi
    if [[ $i -eq 30 ]]; then
      echo "  ui: slow to start — check ${LOG_DIR}/nextjs.log"
    fi
  done
  cd "${REPO}"
fi

echo ""
echo "Kitty is running."
echo "  UI:      http://localhost:${UI_PORT}"
echo "  Gateway: http://localhost:${GW_PORT}"
echo ""
echo "Logs:  ${LOG_DIR}/gateway.log"
echo "       ${LOG_DIR}/nextjs.log"
echo ""
echo "Stop:  bash scripts/stop_cloud.sh"
