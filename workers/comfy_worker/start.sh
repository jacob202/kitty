#!/usr/bin/env bash
set -euo pipefail

: "${KITTY_WORKER_BEARER_TOKEN:?KITTY_WORKER_BEARER_TOKEN is required}"

COMFYUI_ROOT="${COMFYUI_ROOT:-/workspace/ComfyUI}"
COMFYUI_PYTHON="${COMFYUI_PYTHON:-python}"
COMFYUI_HOST="${COMFYUI_HOST:-127.0.0.1}"
COMFYUI_PORT="${COMFYUI_PORT:-8188}"
KITTY_WORKER_PORT="${KITTY_WORKER_PORT:-8000}"

if [[ ! -f "${COMFYUI_ROOT}/main.py" ]]; then
  echo "ComfyUI main.py not found at ${COMFYUI_ROOT}/main.py" >&2
  exit 2
fi

shutdown() {
  kill "${COMFY_PID:-}" "${WORKER_PID:-}" 2>/dev/null || true
  wait "${COMFY_PID:-}" "${WORKER_PID:-}" 2>/dev/null || true
}
trap shutdown EXIT INT TERM

"${COMFYUI_PYTHON}" "${COMFYUI_ROOT}/main.py" \
  --listen "${COMFYUI_HOST}" \
  --port "${COMFYUI_PORT}" &
COMFY_PID=$!

python -m uvicorn workers.comfy_worker.app:create_app \
  --factory \
  --host 0.0.0.0 \
  --port "${KITTY_WORKER_PORT}" &
WORKER_PID=$!

wait -n "${COMFY_PID}" "${WORKER_PID}"
