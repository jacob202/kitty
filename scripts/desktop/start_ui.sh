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

cd "${UI_DIR}"

# `next start` serves the prebuilt .next directory, so a source change that was
# never compiled is invisible at runtime: the UI silently keeps serving an older
# build across every pull. Rebuild whenever a build input is newer than the
# stamp `next build` writes, and let a failed build stop the service rather than
# fall back to serving stale code.
BUILD_STAMP=".next/BUILD_ID"
BUILD_SOURCE_STAMP=".next/KITTY_SOURCE_SHA"

record_build_source() {
  local source_sha
  source_sha="$(git -C "${ROOT_DIR}" rev-parse HEAD 2>/dev/null || true)"
  if [[ -n "${source_sha}" ]]; then
    printf '%s\n' "${source_sha}" > "${BUILD_SOURCE_STAMP}"
  fi
}

build_inputs=()
for candidate in src public package.json package-lock.json tsconfig.json \
  next.config.js next.config.mjs next.config.ts; do
  if [[ -e "${candidate}" ]]; then
    build_inputs+=("${candidate}")
  fi
done

if [[ ! -f "${BUILD_STAMP}" ]]; then
  echo "[start_ui] no usable build in ${UI_DIR}/.next — building"
  npm run build
  record_build_source
else
  # -newer over the whole input set is portable across BSD and GNU find; the
  # first hit is enough, the rest of the list does not need walking.
  stale_input="$(find "${build_inputs[@]}" -newer "${BUILD_STAMP}" -print 2>/dev/null | head -1 || true)"
  if [[ -n "${stale_input}" ]]; then
    echo "[start_ui] ${stale_input} is newer than the last build — rebuilding"
    npm run build
    record_build_source
  else
    echo "[start_ui] build is current — serving .next as-is"
  fi
fi

exec npm run start -- -H "${KITTY_UI_HOST}" -p "${KITTY_UI_PORT}"
