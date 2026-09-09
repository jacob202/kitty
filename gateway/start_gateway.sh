#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"
source "${ROOT_DIR}/gateway/lib/load_env_safe.sh"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  load_env_assignments "${ROOT_DIR}/.env"
fi

export KITTY_ENV="${KITTY_ENV:-prod}"

# AgentRouter credits live on the hosted API. Point to local 9router only by explicit override.
export AGENTROUTER_API_BASE="${AGENTROUTER_API_BASE:-https://agentrouter.org/v1}"

source "${ROOT_DIR}/venv/bin/activate"

if ! command -v uvicorn >/dev/null 2>&1; then
  echo "Error: uvicorn not found in ${ROOT_DIR}/venv"
  exit 1
fi

GATEWAY_HOST="${GATEWAY_HOST:-127.0.0.1}"
GATEWAY_PORT="${GATEWAY_PORT:-8000}"
GATEWAY_RELOAD="${GATEWAY_RELOAD:-0}"

record_runtime_identity() {
  local source_sha dirty run_dir
  source_sha="$(git -C "${ROOT_DIR}" rev-parse HEAD 2>/dev/null || true)"
  [[ -n "${source_sha}" ]] || return 0
  dirty="$(git -C "${ROOT_DIR}" status --porcelain --untracked-files=normal 2>/dev/null || true)"
  [[ -z "${dirty}" ]] || source_sha="dirty:${source_sha}"
  run_dir="${ROOT_DIR}/logs/.run"
  mkdir -p "${run_dir}"
  printf '%s|%s|%s\n' "$$" "${ROOT_DIR}" "${source_sha}" > "${run_dir}/gateway.identity"
}

record_runtime_identity

echo "Starting Kitty Gateway on ${GATEWAY_HOST}:${GATEWAY_PORT}..."
if [[ "${GATEWAY_RELOAD}" == "1" ]]; then
  exec uvicorn gateway.app:app --host "${GATEWAY_HOST}" --port "${GATEWAY_PORT}" --reload
else
  exec uvicorn gateway.app:app --host "${GATEWAY_HOST}" --port "${GATEWAY_PORT}"
fi
