#!/usr/bin/env bash
# start.sh — launch Kitty backend (Flask+SocketIO :5001) + garage-ui (Next.js :3000)
#
# Usage:
#   ./scripts/start.sh              # both servers
#   ./scripts/start.sh --backend    # backend only
#   ./scripts/start.sh --frontend   # frontend only
#   FLASK_DEBUG=1 ./scripts/start.sh  # backend with dev reload

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="$PROJECT_ROOT/venv/bin/python3.12"
GARAGE_UI="$PROJECT_ROOT/garage-ui"

MODE="${1:-both}"

# ── Validation ───────────────────────────────────────────────────────────────
if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "ERROR: venv not found at $PROJECT_ROOT/venv" >&2
  echo "Run: python3.12 -m venv venv && venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

if [[ ! -d "$GARAGE_UI/node_modules" ]]; then
  echo "Installing garage-ui dependencies..."
  cd "$GARAGE_UI" && npm install
fi

cd "$PROJECT_ROOT"

# ── Cleanup on exit ──────────────────────────────────────────────────────────
cleanup() {
  echo ""
  echo "Shutting down..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}

# ── Launch ───────────────────────────────────────────────────────────────────
if [[ "$MODE" == "--backend" ]]; then
  exec "$VENV_PYTHON" web.py

elif [[ "$MODE" == "--frontend" ]]; then
  cd "$GARAGE_UI" && exec npm run dev

else
  trap cleanup EXIT INT TERM

  echo "Starting backend  →  http://localhost:5001"
  "$VENV_PYTHON" web.py &
  BACKEND_PID=$!

  echo "Starting frontend →  http://localhost:3000"
  cd "$GARAGE_UI" && npm run dev &
  FRONTEND_PID=$!

  echo ""
  LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "unknown")

  echo "┌──────────────────────────────────────────────────┐"
  echo "│  🐱  KITTY — full stack running                  │"
  echo "│                                                  │"
  echo "│  Local  UI   →  http://localhost:3000            │"
  echo "│  Local  API  →  http://localhost:5001            │"
  echo "│                                                  │"
  echo "│  Mobile UI   →  http://${LOCAL_IP}:3000          │"
  echo "│  Mobile API  →  http://${LOCAL_IP}:5001          │"
  echo "│                                                  │"
  echo "│  Ctrl+C to stop both                             │"
  echo "└──────────────────────────────────────────────────┘"

  wait
fi
