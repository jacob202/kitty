#!/bin/bash
# Start the Kitty Next.js UI for the desktop service stack (launchd-managed).
#
# Binds loopback only and points the server-side /proxy route at the gateway.
# This wrapper exports KITTY_GATEWAY_URL explicitly so launchd always targets
# the canonical local gateway. Secrets (the gateway bearer) come from .env via
# load_env_safe; none are hard-coded here.
set -euo pipefail

# Resolve repo root from this script's location (scripts/desktop -> root) so the
# wrapper is not tied to one machine's absolute checkout path.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

source "${ROOT_DIR}/gateway/lib/load_env_safe.sh"
if [[ -f "${ROOT_DIR}/.env" ]]; then
  load_env_assignments "${ROOT_DIR}/.env"
fi

UI_DIR="${ROOT_DIR}/gateway/kitty-chat"
KITTY_UI_HOST="${KITTY_UI_HOST:-127.0.0.1}"
KITTY_UI_PORT="${KITTY_UI_PORT:-4000}"
export KITTY_GATEWAY_URL="${KITTY_GATEWAY_URL:-http://127.0.0.1:8000}"

# Diagnostic breadcrumb for "works in Terminal, dies under launchd": log the
# resolved environment with secrets redacted, so a bad PATH or missing var is a
# 30-second read instead of an evening.
echo "[start_ui] root=${ROOT_DIR} host=${KITTY_UI_HOST} port=${KITTY_UI_PORT} gateway=${KITTY_GATEWAY_URL}"
echo "[start_ui] gateway_secret_present=$([[ -n "${KITTY_GATEWAY_SECRET:-}" ]] && echo yes || echo no)"

if ! command -v npm >/dev/null 2>&1; then
  echo "[start_ui] Error: npm not found on PATH (${PATH})" >&2
  exit 1
fi

if [[ ! -d "${UI_DIR}/.next" ]]; then
  echo "[start_ui] Error: ${UI_DIR}/.next is missing. Run 'npm run build' in ${UI_DIR} first." >&2
  exit 1
fi

cd "${UI_DIR}"
exec npm run start -- -H "${KITTY_UI_HOST}" -p "${KITTY_UI_PORT}"
