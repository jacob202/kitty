#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"
source "${ROOT_DIR}/gateway/lib/load_env_safe.sh"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  load_env_assignments "${ROOT_DIR}/.env"
fi

# AgentRouter credits live on the hosted API. Point to local 9router only by explicit override.
export AGENTROUTER_API_BASE="${AGENTROUTER_API_BASE:-https://agentrouter.org/v1}"

LITELLM_VENV="${LITELLM_VENV:-${HOME}/kitty-services/venv-litellm}"
source "${LITELLM_VENV}/bin/activate"

LITELLM_HOST="${LITELLM_HOST:-127.0.0.1}"
LITELLM_PORT="${LITELLM_PORT:-8001}"
LITELLM_CONFIG="${LITELLM_CONFIG:-gateway/litellm_config.yaml}"
LITELLM_REQUIREMENTS_FILE="${LITELLM_REQUIREMENTS_FILE:-gateway/requirements.litellm.txt}"
LITELLM_AUTO_REPAIR="${LITELLM_AUTO_REPAIR:-0}"
export LITELLM_MASTER_KEY="${LITELLM_MASTER_KEY:-kitty-local-key-change-me}"
export LITELLM_MAX_BUDGET_USD="${LITELLM_MAX_BUDGET_USD:-2.00}"

if [[ "${LITELLM_CONFIG}" = /* ]]; then
  LITELLM_CONFIG_PATH="${LITELLM_CONFIG}"
else
  LITELLM_CONFIG_PATH="${ROOT_DIR}/${LITELLM_CONFIG}"
fi

if [[ ! -f "${LITELLM_CONFIG_PATH}" ]]; then
  echo "Error: LiteLLM config not found at ${LITELLM_CONFIG_PATH}."
  exit 1
fi

# LiteLLM has its own isolated environment. An inherited Kitty PYTHONPATH makes
# the repo's mcp/ package shadow LiteLLM's installed MCP SDK.
unset PYTHONPATH

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
echo "Config: ${LITELLM_CONFIG_PATH}"
echo "Daily budget (USD): ${LITELLM_MAX_BUDGET_USD}"

if [[ "${LITELLM_SMOKE:-0}" == "1" ]]; then
  echo "LITELLM_SMOKE=1 set; exiting before server start."
  exit 0
fi

# Starting outside the repo prevents Kitty's local mcp/ package from shadowing
# the MCP SDK imported by LiteLLM's proxy runtime.
cd "${LITELLM_VENV}"
litellm --config "${LITELLM_CONFIG_PATH}" --port "${LITELLM_PORT}" --host "${LITELLM_HOST}"
