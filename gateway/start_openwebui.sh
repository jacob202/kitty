#!/bin/bash
set -euo pipefail

OPENWEBUI_VENV="${OPENWEBUI_VENV:-${HOME}/kitty-services/venv}"
source "${OPENWEBUI_VENV}/bin/activate"
source "gateway/lib/load_env_safe.sh"

if [[ -f ".env" ]]; then
  load_env_assignments ".env"
fi

# AgentRouter credits live on the hosted API. Point to local 9router only by explicit override.
export AGENTROUTER_API_BASE="${AGENTROUTER_API_BASE:-https://agentrouter.org/v1}"

# Export every assignment from openwebui.env — Open WebUI only sees **exported**
# vars. Without `set -a`, DISABLE_OLLAMA / DEFAULT_MODELS / multi-endpoint keys stay
# shell-local and WebUI falls back to wrong backends (looks like “GPT direct” chaos).
if [[ -f "kitty_gateway/openwebui.env" ]]; then
  load_env_assignments "kitty_gateway/openwebui.env"
fi

if [[ -n "${OPENWEBUI_DATA_DIR_OVERRIDE:-}" ]]; then
  OPENWEBUI_DATA_DIR="${OPENWEBUI_DATA_DIR_OVERRIDE}"
fi
if [[ -n "${OPENWEBUI_SECRET_FILE_OVERRIDE:-}" ]]; then
  OPENWEBUI_SECRET_FILE="${OPENWEBUI_SECRET_FILE_OVERRIDE}"
fi

OPENWEBUI_DATA_DIR="${OPENWEBUI_DATA_DIR:-${HOME}/kitty-services/open-webui-data}"
mkdir -p "${OPENWEBUI_DATA_DIR}"

SECRET_FILE="${OPENWEBUI_SECRET_FILE:-${OPENWEBUI_DATA_DIR}/.webui_secret}"
if [[ -z "${WEBUI_SECRET_KEY:-}" ]]; then
  if [[ -f "${SECRET_FILE}" ]]; then
    WEBUI_SECRET_KEY="$(cat "${SECRET_FILE}")"
  else
    WEBUI_SECRET_KEY="$(/opt/homebrew/bin/python3.12 -c 'import secrets; print(secrets.token_urlsafe(48))')"
    printf "%s" "${WEBUI_SECRET_KEY}" > "${SECRET_FILE}"
    chmod 600 "${SECRET_FILE}"
  fi
fi

export DATA_DIR="${OPENWEBUI_DATA_DIR}"
export OPENAI_API_BASE_URL="${OPENAI_API_BASE_URL:-${LITELLM_BASE:-http://127.0.0.1:8001}/v1}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-${LITELLM_KEY:-kitty-local-key-change-me}}"
export WEBUI_SECRET_KEY
export DEFAULT_MODELS="${DEFAULT_MODELS:-kitty-default}"
export WEBUI_NAME="${WEBUI_NAME:-Kitty WebUI}"
export OFFLINE_MODE="${OFFLINE_MODE:-true}"
export ENABLE_VERSION_UPDATE_CHECK="${ENABLE_VERSION_UPDATE_CHECK:-false}"
export GLOBAL_LOG_LEVEL="${GLOBAL_LOG_LEVEL:-WARNING}"
export ENABLE_PROFILE_IMAGE_URL_FORWARDING="${ENABLE_PROFILE_IMAGE_URL_FORWARDING:-false}"

OPENWEBUI_PORT="${OPENWEBUI_PORT:-3000}"
OPENWEBUI_HOST="${OPENWEBUI_HOST:-127.0.0.1}"
export WEBUI_URL="http://${OPENWEBUI_HOST}:${OPENWEBUI_PORT}"

echo "Starting Open WebUI on port ${OPENWEBUI_PORT}..."
echo "Interface: ${WEBUI_URL}"
echo "Data dir: ${DATA_DIR}"
echo "Model endpoint: ${OPENAI_API_BASE_URL}"

if ! curl -fsS --max-time 2 "${OPENAI_API_BASE_URL%/v1}/health" >/dev/null 2>&1; then
  echo "Warning: LiteLLM endpoint is not healthy yet (${OPENAI_API_BASE_URL})."
  echo "OpenWebUI will still start, but model list may be empty until LiteLLM is up."
fi

if [[ "${OPENWEBUI_SMOKE:-0}" == "1" ]]; then
  echo "OPENWEBUI_SMOKE=1 set; exiting before server start."
  exit 0
fi

exec open-webui serve --host "${OPENWEBUI_HOST}" --port "${OPENWEBUI_PORT}"
