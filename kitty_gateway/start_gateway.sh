#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/jacobbrizinski/Projects/kitty"
cd "${ROOT_DIR}"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi

source "${ROOT_DIR}/venv/bin/activate"

if ! command -v uvicorn >/dev/null 2>&1; then
  echo "Error: uvicorn not found in ${ROOT_DIR}/venv"
  exit 1
fi

GATEWAY_HOST="${GATEWAY_HOST:-127.0.0.1}"
GATEWAY_PORT="${GATEWAY_PORT:-8000}"
GATEWAY_RELOAD="${GATEWAY_RELOAD:-0}"

echo "Starting Kitty Gateway on ${GATEWAY_HOST}:${GATEWAY_PORT}..."
if [[ "${GATEWAY_RELOAD}" == "1" ]]; then
  exec uvicorn gateway.app:app --host "${GATEWAY_HOST}" --port "${GATEWAY_PORT}" --reload
else
  exec uvicorn gateway.app:app --host "${GATEWAY_HOST}" --port "${GATEWAY_PORT}"
fi
