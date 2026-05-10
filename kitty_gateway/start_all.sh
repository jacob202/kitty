#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/jacobbrizinski/Projects/kitty"
RUN_DIR="${ROOT_DIR}/kitty_gateway/.run"
LOG_DIR="${ROOT_DIR}/logs/kitty_gateway"
ENABLE_MLX="${ENABLE_MLX:-0}"
ENABLE_LITELLM="${ENABLE_LITELLM:-1}"
ENABLE_GATEWAY="${ENABLE_GATEWAY:-1}"
ENABLE_OPENWEBUI="${ENABLE_OPENWEBUI:-1}"
ENABLE_JUPYTER="${ENABLE_JUPYTER:-1}"
ENABLE_OPEN_TERMINAL="${ENABLE_OPEN_TERMINAL:-1}"
ENABLE_COMMUNITY_TOOL_SERVERS="${ENABLE_COMMUNITY_TOOL_SERVERS:-1}"
ENABLE_CLOUDFLARE_HTTPS="${ENABLE_CLOUDFLARE_HTTPS:-0}"
AUTO_SYNC_OPENWEBUI_INTEGRATIONS="${AUTO_SYNC_OPENWEBUI_INTEGRATIONS:-1}"
AUTO_IMPORT_OPENWEBUI_FUNCTIONS="${AUTO_IMPORT_OPENWEBUI_FUNCTIONS:-1}"
ASSERT_BASELINE_ON_BOOT="${ASSERT_BASELINE_ON_BOOT:-1}"
ASSERT_FAIL_ON_WARN="${ASSERT_FAIL_ON_WARN:-0}"
START_ALL_SMOKE="${START_ALL_SMOKE:-0}"

mkdir -p "${RUN_DIR}" "${LOG_DIR}"
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

service_pattern() {
  local name="$1"
  case "${name}" in
    mlx) echo "mlx_lm.server" ;;
    litellm) echo "venv-litellm/bin/litellm --config kitty_gateway/litellm_config.yaml" ;;
    gateway) echo "venv/bin/uvicorn gateway.app:app --host 127.0.0.1 --port 8000" ;;
    openwebui) echo "venv/bin/open-webui serve" ;;
    jupyter) echo "venv/bin/jupyter.*lab.*--ip=127.0.0.1.*--port=8888" ;;
    cloudflare) echo "cloudflared tunnel" ;;
    openterminal) echo "venv/bin/open-terminal run --host 127.0.0.1 --port" ;;
    tool-filesystem) echo "uvicorn main:app --host 127.0.0.1 --port 9721" ;;
    tool-memory) echo "uvicorn main:app --host 127.0.0.1 --port 9722" ;;
    tool-time) echo "uvicorn main:app --host 127.0.0.1 --port 9723" ;;
    tool-weather) echo "uvicorn main:app --host 127.0.0.1 --port 9724" ;;
    *) echo "" ;;
  esac
}

start_service() {
  local name="$1"
  local cmd="$2"
  local pid_file="${RUN_DIR}/${name}.pid"
  local log_file="${LOG_DIR}/${name}.log"
  local pattern
  pattern="$(service_pattern "${name}")"

  if pgrep -f "${pattern}" >/dev/null 2>&1; then
    local running_pid
    running_pid="$(pgrep -f "${pattern}" | head -n1)"
    echo "${name}: already running (pid ${running_pid})"
    echo "${running_pid}" > "${pid_file}"
    return 0
  fi

  echo "Starting ${name}..."
  nohup bash -lc "${cmd}" >"${log_file}" 2>&1 &
  local launcher_pid=$!
  local pid="${launcher_pid}"
  echo "${pid}" > "${pid_file}"
  sleep 2

  if pgrep -f "${pattern}" >/dev/null 2>&1; then
    pid="$(pgrep -f "${pattern}" | head -n1)"
    echo "${pid}" > "${pid_file}"
  elif ! kill -0 "${launcher_pid}" 2>/dev/null; then
    echo "${name}: failed to start. See ${log_file}"
    return 1
  fi
  echo "${name}: started (pid ${pid})"
}

wait_http() {
  local name="$1"
  local url="$2"
  local auth_header="${3:-}"
  local retries="${4:-30}"
  local delay="${5:-1}"
  local max_time="${6:-2}"
  local i

  for ((i=1; i<=retries; i++)); do
    if [[ -n "${auth_header}" ]]; then
      if curl -fsS --max-time "${max_time}" -H "${auth_header}" "${url}" >/dev/null 2>&1; then
        echo "${name}: healthy (${url})"
        return 0
      fi
    elif curl -fsS --max-time "${max_time}" "${url}" >/dev/null 2>&1; then
      echo "${name}: healthy (${url})"
      return 0
    fi
    sleep "${delay}"
  done
  echo "${name}: not healthy yet (${url})"
  return 1
}

if [[ ! -f "${ROOT_DIR}/kitty_gateway/openwebui.env" ]]; then
  echo "Notice: kitty_gateway/openwebui.env not found."
  echo "Copy kitty_gateway/openwebui.env.example to openwebui.env to set admin/image/search settings."
fi

if [[ "${START_ALL_SMOKE}" == "1" ]]; then
  [[ "${ENABLE_MLX}" == "1" ]] && MLX_SMOKE=1 bash kitty_gateway/start_mlx.sh
  [[ "${ENABLE_LITELLM}" == "1" ]] && LITELLM_SMOKE=1 bash kitty_gateway/start_litellm.sh
  [[ "${ENABLE_GATEWAY}" == "1" ]] && echo "Gateway smoke skipped (launcher is runtime-only)."
  [[ "${ENABLE_OPENWEBUI}" == "1" ]] && OPENWEBUI_SMOKE=1 bash kitty_gateway/start_openwebui.sh
  [[ "${ENABLE_JUPYTER}" == "1" ]] && echo "Jupyter smoke skipped (launcher is runtime-only)."
  [[ "${ENABLE_OPEN_TERMINAL}" == "1" ]] && echo "Open Terminal smoke skipped (launcher is runtime-only)."
  [[ "${ENABLE_COMMUNITY_TOOL_SERVERS}" == "1" ]] && echo "Community tool servers smoke skipped (launcher is runtime-only)."
  [[ "${ENABLE_CLOUDFLARE_HTTPS}" == "1" ]] && echo "Cloudflare smoke skipped (runtime/external only)."
  echo "Smoke checks complete."
  exit 0
fi

if [[ "${ENABLE_MLX}" == "1" ]]; then
  start_service "mlx" "cd '${ROOT_DIR}' && bash kitty_gateway/start_mlx.sh"
fi
if [[ "${ENABLE_LITELLM}" == "1" ]]; then
  start_service "litellm" "cd '${ROOT_DIR}' && bash kitty_gateway/start_litellm.sh"
fi
if [[ "${ENABLE_GATEWAY}" == "1" ]]; then
  start_service "gateway" "cd '${ROOT_DIR}' && bash kitty_gateway/start_gateway.sh"
fi
if [[ "${ENABLE_OPENWEBUI}" == "1" ]]; then
  start_service "openwebui" "cd '${ROOT_DIR}' && bash kitty_gateway/start_openwebui.sh"
fi
if [[ "${ENABLE_JUPYTER}" == "1" ]]; then
  start_service "jupyter" "cd '${ROOT_DIR}' && bash kitty_gateway/start_jupyter_exec.sh"
fi
if [[ "${ENABLE_OPEN_TERMINAL}" == "1" ]]; then
  start_service "openterminal" "cd '${ROOT_DIR}' && bash kitty_gateway/start_open_terminal.sh"
fi
if [[ "${ENABLE_COMMUNITY_TOOL_SERVERS}" == "1" ]]; then
  bash kitty_gateway/start_tool_servers.sh
fi
if [[ "${ENABLE_CLOUDFLARE_HTTPS}" == "1" ]]; then
  start_service "cloudflare" "cd '${ROOT_DIR}' && bash kitty_gateway/start_cloudflare_https.sh"
fi

[[ "${ENABLE_LITELLM}" == "1" ]] && wait_http "litellm" "http://127.0.0.1:8001/health" "Authorization: Bearer ${LITELLM_MASTER_KEY:-kitty-local-key-change-me}" 30 1 8 || true
[[ "${ENABLE_GATEWAY}" == "1" ]] && wait_http "gateway" "http://127.0.0.1:8000/health" || true
[[ "${ENABLE_OPENWEBUI}" == "1" ]] && wait_http "openwebui" "http://127.0.0.1:3000/health" || true
[[ "${ENABLE_JUPYTER}" == "1" ]] && wait_http "jupyter" "http://127.0.0.1:8888/api" "Authorization: token ${CODE_EXECUTION_JUPYTER_AUTH_TOKEN:-}" || true
[[ "${ENABLE_OPEN_TERMINAL}" == "1" ]] && wait_http "openterminal" "${OPEN_TERMINAL_URL:-http://127.0.0.1:9614}/health" || true
[[ "${ENABLE_COMMUNITY_TOOL_SERVERS}" == "1" ]] && wait_http "tool-filesystem" "http://127.0.0.1:9721/openapi.json" || true
[[ "${ENABLE_COMMUNITY_TOOL_SERVERS}" == "1" ]] && wait_http "tool-memory" "http://127.0.0.1:9722/openapi.json" || true
[[ "${ENABLE_COMMUNITY_TOOL_SERVERS}" == "1" ]] && wait_http "tool-time" "http://127.0.0.1:9723/openapi.json" || true
[[ "${ENABLE_COMMUNITY_TOOL_SERVERS}" == "1" ]] && wait_http "tool-weather" "http://127.0.0.1:9724/openapi.json" || true

if [[ "${ENABLE_OPENWEBUI}" == "1" && "${AUTO_SYNC_OPENWEBUI_INTEGRATIONS}" == "1" ]]; then
  bash kitty_gateway/sync_openwebui_integrations.sh || true
fi
if [[ "${ENABLE_OPENWEBUI}" == "1" && "${AUTO_IMPORT_OPENWEBUI_FUNCTIONS}" == "1" ]]; then
  bash kitty_gateway/import_openwebui_functions.sh || true
fi
if [[ "${ENABLE_OPENWEBUI}" == "1" && "${ASSERT_BASELINE_ON_BOOT}" == "1" ]]; then
  if [[ "${ASSERT_FAIL_ON_WARN}" == "1" ]]; then
    bash kitty_gateway/doctor.sh --fail-on-warn || {
      echo "Baseline assertion failed (fail-on-warn enabled)."
      exit 1
    }
  else
    bash kitty_gateway/doctor.sh || {
      echo "Baseline assertion failed (hard failures present)."
      exit 1
    }
  fi
fi

echo
echo "Stack launch complete."
echo "UI:      http://127.0.0.1:3000"
echo "Gateway: http://127.0.0.1:8000"
echo "LiteLLM: http://127.0.0.1:8001"
echo "MLX:     http://127.0.0.1:8010"
echo
echo "Logs:"
echo "  ${LOG_DIR}/mlx.log"
echo "  ${LOG_DIR}/litellm.log"
echo "  ${LOG_DIR}/openwebui.log"
echo "  ${LOG_DIR}/jupyter.log"
echo "  ${LOG_DIR}/open-terminal.log"
echo "  ${LOG_DIR}/tool-filesystem.log"
echo "  ${LOG_DIR}/tool-memory.log"
echo "  ${LOG_DIR}/tool-time.log"
echo "  ${LOG_DIR}/tool-weather.log"
echo "  ${LOG_DIR}/cloudflare.log"
echo
echo "Use: bash kitty_gateway/status_all.sh"
echo "Use: bash kitty_gateway/stop_all.sh"
