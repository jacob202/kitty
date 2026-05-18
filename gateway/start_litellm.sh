#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/jacobbrizinski/Projects/kitty"
cd "${ROOT_DIR}"
source "${ROOT_DIR}/gateway/lib/load_env_safe.sh"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  load_env_assignments "${ROOT_DIR}/.env"
fi

# AgentRouter credits live on the hosted API. Point to local 9router only by explicit override.
export AGENTROUTER_API_BASE="${AGENTROUTER_API_BASE:-https://agentrouter.org/v1}"

if [[ -f "${ROOT_DIR}/kitty_gateway/openwebui.env" ]]; then
  load_env_assignments "${ROOT_DIR}/kitty_gateway/openwebui.env"
fi

LITELLM_VENV="${LITELLM_VENV:-${HOME}/kitty-services/venv-litellm}"
source "${LITELLM_VENV}/bin/activate"

LITELLM_HOST="${LITELLM_HOST:-127.0.0.1}"
LITELLM_PORT="${LITELLM_PORT:-8001}"
LITELLM_CONFIG="${LITELLM_CONFIG:-gateway/litellm_config.yaml}"
LITELLM_REQUIREMENTS_FILE="${LITELLM_REQUIREMENTS_FILE:-gateway/requirements.litellm.txt}"
LITELLM_AUTO_REPAIR="${LITELLM_AUTO_REPAIR:-0}"
export LITELLM_MASTER_KEY="${LITELLM_MASTER_KEY:-kitty-local-key-change-me}"
export LITELLM_MAX_BUDGET_USD="${LITELLM_MAX_BUDGET_USD:-2.00}"

if ! command -v litellm >/dev/null 2>&1; then
  echo "Error: litellm CLI not found in ${LITELLM_VENV}."
  exit 1
fi

if ! python - <<'PY' >/dev/null 2>&1
import importlib.metadata as md
import litellm.constants as c
assert hasattr(c, "COMPETITOR_LLM_TEMPERATURE")
assert md.version("openai") == "2.24.0"
PY
then
  echo "Error: LiteLLM installation appears inconsistent for proxy mode."
  if [[ "${LITELLM_AUTO_REPAIR}" == "1" ]]; then
    echo "Attempting auto-repair from ${LITELLM_REQUIREMENTS_FILE}..."
    pip install --upgrade -r "${LITELLM_REQUIREMENTS_FILE}"
  else
    echo "Fix:"
    echo "  source ${LITELLM_VENV}/bin/activate"
    echo "  pip install --upgrade -r ${LITELLM_REQUIREMENTS_FILE}"
    echo "Or run auto-repair:"
    echo "  LITELLM_AUTO_REPAIR=1 bash gateway/start_litellm.sh"
    exit 1
  fi
fi

if ! python - <<'PY' >/dev/null 2>&1
import importlib.metadata as md
import litellm.constants as c
assert hasattr(c, "COMPETITOR_LLM_TEMPERATURE")
assert md.version("openai") == "2.24.0"
PY
then
  echo "Error: LiteLLM preflight still failing after repair attempt."
  exit 1
fi

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "Warning: OPENROUTER_API_KEY is not set. Remote models will fail."
fi

echo "Starting LiteLLM proxy on ${LITELLM_HOST}:${LITELLM_PORT}..."
echo "Config: ${LITELLM_CONFIG}"
echo "Daily budget (USD): ${LITELLM_MAX_BUDGET_USD}"

if [[ "${LITELLM_SMOKE:-0}" == "1" ]]; then
  echo "LITELLM_SMOKE=1 set; exiting before server start."
  exit 0
fi

litellm --config "${LITELLM_CONFIG}" --port "${LITELLM_PORT}" --host "${LITELLM_HOST}"
