#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/jacobbrizinski/Projects/kitty"
LOG_DIR="${ROOT_DIR}/logs/kitty_gateway"
RUN_DIR="${ROOT_DIR}/kitty_gateway/.run"
TARGET_URL="${CF_TUNNEL_TARGET_URL:-http://127.0.0.1:3000}"
TOKEN="${CF_TUNNEL_TOKEN:-}"
TOKEN_FILE="${CF_TUNNEL_TOKEN_FILE:-}"
MODE="${CF_TUNNEL_MODE:-quick}"

mkdir -p "${LOG_DIR}" "${RUN_DIR}"
cd "${ROOT_DIR}"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi
if [[ -f "${ROOT_DIR}/kitty_gateway/openwebui.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/kitty_gateway/openwebui.env"
  set +a
fi

# Re-evaluate after env load.
TARGET_URL="${CF_TUNNEL_TARGET_URL:-${TARGET_URL}}"
TOKEN="${CF_TUNNEL_TOKEN:-${TOKEN}}"
TOKEN_FILE="${CF_TUNNEL_TOKEN_FILE:-${TOKEN_FILE}}"
MODE="${CF_TUNNEL_MODE:-${MODE}}"
MODE="$(printf "%s" "${MODE}" | tr '[:upper:]' '[:lower:]')"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared not found. Install with: brew install cloudflared"
  exit 1
fi

if pgrep -f "cloudflared tunnel" >/dev/null 2>&1; then
  echo "Cloudflare tunnel already running."
  exit 0
fi

if [[ "${MODE}" == "named" ]]; then
  if [[ -n "${TOKEN_FILE}" ]]; then
    nohup cloudflared tunnel --no-autoupdate run --token-file "${TOKEN_FILE}" > "${LOG_DIR}/cloudflare.log" 2>&1 < /dev/null &
  elif [[ -n "${TOKEN}" ]]; then
    nohup cloudflared tunnel --no-autoupdate run --token "${TOKEN}" > "${LOG_DIR}/cloudflare.log" 2>&1 < /dev/null &
  else
    echo "CF_TUNNEL_MODE=named requires CF_TUNNEL_TOKEN or CF_TUNNEL_TOKEN_FILE."
    exit 1
  fi
else
  if [[ "${MODE}" != "quick" ]]; then
    echo "Unknown CF_TUNNEL_MODE='${MODE}'. Use 'quick' or 'named'."
    exit 1
  fi
  nohup cloudflared tunnel --url "${TARGET_URL}" --no-autoupdate > "${LOG_DIR}/cloudflare.log" 2>&1 < /dev/null &
fi
echo $! > "${RUN_DIR}/cloudflare.pid"
sleep 3

URL="$(grep -Eo "https://[a-z0-9-]+\\.trycloudflare\\.com" "${LOG_DIR}/cloudflare.log" | head -n1 || true)"
if [[ -n "${URL}" ]]; then
  echo "Cloudflare tunnel URL: ${URL}"
else
  echo "Cloudflare tunnel started. Check log: ${LOG_DIR}/cloudflare.log"
fi
