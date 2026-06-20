#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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

LITELLM_URL="${OPENAI_API_BASE_URL:-http://127.0.0.1:8001/v1}"
LITELLM_BASE="${LITELLM_URL%/v1}"
MASTER_KEY="${LITELLM_MASTER_KEY:-${OPENAI_API_KEY:-}}"
OPENWEBUI_URL="${WEBUI_URL:-http://127.0.0.1:3000}"

ok() { echo "OK   - $*"; }
warn() { echo "WARN - $*"; }
fail() { echo "FAIL - $*"; }

echo "== Kitty Gateway Model Diagnostics =="
echo "Litellm URL: ${LITELLM_URL}"
echo "OpenWebUI:  ${OPENWEBUI_URL}"
echo

# Preflight: secrets + routing
[[ -n "${OPENROUTER_API_KEY:-}" ]] && ok "OPENROUTER_API_KEY is present" || fail "OPENROUTER_API_KEY missing"
[[ -n "${MASTER_KEY:-}" ]] && ok "LiteLLM master key is present" || fail "LiteLLM master key missing (LITELLM_MASTER_KEY / OPENAI_API_KEY)"

echo
echo "== Service Health =="
if curl -fsS --max-time 2 -H "Authorization: Bearer ${MASTER_KEY}" "${LITELLM_BASE}/health" >/dev/null 2>&1; then
  ok "LiteLLM health endpoint is up (${LITELLM_BASE}/health)"
  litellm_up=1
else
  fail "LiteLLM health endpoint is down (${LITELLM_BASE}/health)"
  litellm_up=0
fi

if curl -fsS --max-time 2 "${OPENWEBUI_URL%/}/health" >/dev/null 2>&1; then
  ok "OpenWebUI health endpoint is up (${OPENWEBUI_URL%/}/health)"
else
  warn "OpenWebUI health endpoint is down (${OPENWEBUI_URL%/}/health)"
fi

if curl -fsS --max-time 2 "http://127.0.0.1:8010/v1/models" >/dev/null 2>&1; then
  ok "MLX endpoint is up (http://127.0.0.1:8010/v1/models)"
  mlx_up=1
else
  warn "MLX endpoint is down (http://127.0.0.1:8010/v1/models)"
  mlx_up=0
fi

echo
echo "== LiteLLM Model Visibility =="
models_json=""
if [[ "${litellm_up}" == "1" && -n "${MASTER_KEY:-}" ]]; then
  if models_json="$(curl -fsS --max-time 5 "${LITELLM_URL}/models" -H "Authorization: Bearer ${MASTER_KEY}" 2>/dev/null)"; then
    ok "Fetched model list from LiteLLM /v1/models"
  else
    fail "Could not fetch /v1/models with current master key"
  fi
fi

model_names=""
if [[ -n "${models_json}" ]]; then
  model_names="$(python3 - <<'PY' "${models_json}"
import json, sys
try:
    payload = json.loads(sys.argv[1])
    names = [x.get("id","") for x in payload.get("data", []) if isinstance(x, dict)]
    print("\n".join(n for n in names if n))
except Exception:
    pass
PY
)"
  if [[ -n "${model_names}" ]]; then
    echo "${model_names}" | sed 's/^/  - /'
  else
    warn "No model IDs returned by /v1/models"
  fi
fi

echo
echo "== Alias Diagnosis =="
alias="kitty-default"
if [[ "${litellm_up}" != "1" ]]; then
  fail "${alias}: unavailable because LiteLLM is down"
elif [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  fail "${alias}: unavailable because OPENROUTER_API_KEY is missing"
elif echo "${model_names}" | grep -qx "${alias}"; then
  ok "${alias}: available in /v1/models"
else
  warn "${alias}: LiteLLM is up but alias not listed in /v1/models"
fi

echo
echo "== Feature Config Checks (Admin) =="
[[ "${ENABLE_WEB_SEARCH:-false}" == "true" ]] && ok "Web search enabled" || warn "Web search disabled"
if [[ "${ENABLE_WEB_SEARCH:-false}" == "true" ]]; then
  if [[ -n "${BRAVE_SEARCH_API_KEY:-}" || -n "${TAVILY_API_KEY:-}" || -n "${SEARXNG_QUERY_URL:-}" ]]; then
    ok "Search provider appears configured"
  else
    warn "No web search provider configured (BRAVE_SEARCH_API_KEY / TAVILY_API_KEY / SEARXNG_QUERY_URL)"
  fi
fi

[[ "${ENABLE_IMAGE_GENERATION:-false}" == "true" ]] && ok "Image generation enabled" || warn "Image generation disabled"
[[ "${ENABLE_CODE_EXECUTION:-false}" == "true" ]] && ok "Code execution enabled" || warn "Code execution disabled"
if [[ "${ENABLE_CODE_EXECUTION:-false}" == "true" ]]; then
  [[ -n "${CODE_EXECUTION_JUPYTER_AUTH_TOKEN:-}" ]] && ok "Jupyter token configured for code execution" || warn "Jupyter token missing for code execution"
fi
