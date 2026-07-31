#!/usr/bin/env bash
set -euo pipefail

# Image-baked bootstrap. No source is downloaded at runtime: the worker app,
# workflow bundle, and start scripts ship inside the image. The only runtime
# fetch is the checkpoint model (large, deliberately not baked), which is
# verified against a pinned SHA-256 and cached on the workspace volume so a
# matching copy skips the download on subsequent starts.

: "${KITTY_WORKER_BEARER_TOKEN:?KITTY_WORKER_BEARER_TOKEN is required}"
: "${COMFY_CHECKPOINT:?COMFY_CHECKPOINT is required}"

export KITTY_STATE_FILE="${KITTY_STATE_FILE:-/tmp/kitty-state.json}"
export KITTY_STAGE_PIDFILE="${KITTY_STAGE_PIDFILE:-/tmp/kitty-stage.pid}"

PYTHON_BIN="${COMFYUI_PYTHON:-python}"
WORKSPACE="${KITTY_WORKSPACE:-/workspace}"
MODEL_CACHE_DIR="${KITTY_MODEL_CACHE_DIR:-${WORKSPACE}/kitty-models}"
STAGE_SERVER_PID=""

set_state() {
  local state_status="$1"
  local state_stage="$2"
  local state_code="${3:-}"
  local state_error="${4:-}"
  python3 - "$state_status" "$state_stage" "$state_code" "$state_error" <<'PY'
import json
import os
import sys
import time

status, stage, code, error = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
payload = {
    "status": status,
    "stage": stage,
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "image_digest": os.environ.get("KITTY_IMAGE_DIGEST", "unknown"),
}
if code:
    payload["exit_code"] = int(code)
if error:
    payload["error"] = error
try:
    with open(os.environ["KITTY_STATE_FILE"], "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload))
except OSError:
    pass
PY
}

stop_stage_server() {
  if [[ -n "${STAGE_SERVER_PID}" ]]; then
    kill "${STAGE_SERVER_PID}" 2>/dev/null || true
    wait "${STAGE_SERVER_PID}" 2>/dev/null || true
    STAGE_SERVER_PID=""
  fi
  if [[ -f "${KITTY_STAGE_PIDFILE}" ]]; then
    kill "$(cat "${KITTY_STAGE_PIDFILE}")" 2>/dev/null || true
    wait "$(cat "${KITTY_STAGE_PIDFILE}")" 2>/dev/null || true
    rm -f "${KITTY_STAGE_PIDFILE}"
  fi
}

fail() {
  local message="$1"
  local current_stage
  current_stage="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('stage','unknown'))" "${KITTY_STATE_FILE}" 2>/dev/null || echo unknown)"
  echo "kitty bootstrap failed at stage ${current_stage}: ${message}" >&2
  set_state failed "${current_stage}" 1 "${message}"
  stop_stage_server
  exit 1
}

trap stop_stage_server EXIT

set_state starting bootstrap-starting

# --- base-validating -----------------------------------------------------
set_state starting base-validating
COMFYUI_ROOT="${COMFYUI_ROOT:-${WORKSPACE}/ComfyUI}"
if [[ ! -f "${COMFYUI_ROOT}/main.py" ]]; then
  DISCOVERED_MAIN="$(find "${WORKSPACE}" /opt /app -type f -path '*/ComfyUI/main.py' -print -quit 2>/dev/null || true)"
  if [[ -z "${DISCOVERED_MAIN}" ]]; then
    fail "ComfyUI/main.py not found under ${WORKSPACE}, /opt, /app (baked base image mismatch)"
  fi
  COMFYUI_ROOT="$(dirname "${DISCOVERED_MAIN}")"
fi
export COMFYUI_ROOT
"${PYTHON_BIN}" -c "import workers.comfy_worker.app" || fail "worker app import failed (baked image missing dependency?)"
echo "kitty bootstrap: ComfyUI root ${COMFYUI_ROOT}"

# --- checkpoint-resolving -------------------------------------------------
set_state starting checkpoint-resolving
CHECKPOINT_DIR="${COMFYUI_ROOT}/models/checkpoints"
mkdir -p "${CHECKPOINT_DIR}" "${MODEL_CACHE_DIR}" "${KITTY_JOB_ROOT:-${WORKSPACE}/jobs}" 2>/dev/null || fail "workspace volumes not writable"
CHECKPOINT_PATH="${CHECKPOINT_DIR}/${COMFY_CHECKPOINT}"
CACHED_CHECKPOINT="${MODEL_CACHE_DIR}/${COMFY_CHECKPOINT}"

available_and_verified() {
  local path="$1"
  [[ -s "${path}" ]] || return 1
  if [[ -n "${COMFY_CHECKPOINT_SHA256:-}" ]]; then
    local digest
    digest="$("${PYTHON_BIN}" -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "${path}" 2>/dev/null || echo "")"
    [[ "${digest}" == "${COMFY_CHECKPOINT_SHA256}" ]]
  else
    echo "kitty bootstrap: warning: no COMFY_CHECKPOINT_SHA256 set; trusting existing file size" >&2
  fi
}

if [[ -f "${CHECKPOINT_PATH}" ]] && available_and_verified "${CHECKPOINT_PATH}"; then
  echo "kitty bootstrap: checkpoint already present and verified at ${CHECKPOINT_PATH}"
elif [[ -f "${CACHED_CHECKPOINT}" ]] && available_and_verified "${CACHED_CHECKPOINT}"; then
  cp -n "${CACHED_CHECKPOINT}" "${CHECKPOINT_PATH}" || cp "${CACHED_CHECKPOINT}" "${CHECKPOINT_PATH}"
  echo "kitty bootstrap: checkpoint restored from verified cache ${CACHED_CHECKPOINT}"
elif [[ -n "${COMFY_CHECKPOINT_URL:-}" ]]; then
  "${PYTHON_BIN}" - "${COMFY_CHECKPOINT_URL}" "${CACHED_CHECKPOINT}" <<'PY' || fail "checkpoint download failed"
import hashlib
import os
import sys
import urllib.request

url, target = sys.argv[1], sys.argv[2]
expected = os.environ.get("COMFY_CHECKPOINT_SHA256", "")
hash_alg = hashlib.sha256()
done = False
try:
    with urllib.request.urlopen(url, timeout=180) as response, open(target, "wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
            hash_alg.update(chunk)
    done = True
finally:
    pass
if expected and hash_alg.hexdigest() != expected:
    print(f"checkpoint sha256 mismatch: got {hash_alg.hexdigest()} expected {expected}", file=sys.stderr)
    os.remove(target)
    sys.exit(1)
if not done:
    sys.exit(1)
PY
  cp -n "${CACHED_CHECKPOINT}" "${CHECKPOINT_PATH}" || cp "${CACHED_CHECKPOINT}" "${CHECKPOINT_PATH}"
  echo "kitty bootstrap: checkpoint downloaded and verified"
elif [[ "${KITTY_PREFLIGHT:-0}" == "1" ]]; then
  echo "kitty bootstrap: preflight mode — skipping checkpoint resolution"
else
  fail "checkpoint ${COMFY_CHECKPOINT} not found and COMFY_CHECKPOINT_URL is unset"
fi

if [[ "${KITTY_PREFLIGHT:-0}" == "1" ]]; then
  echo "kitty bootstrap: preflight mode — not launching ComfyUI (no GPU in CI)"
  set_state ready ready
  echo "PREFLIGHT_OK stage=ready"
  while true; do
    sleep 3600
  done
fi

# --- comfy-booting -------------------------------------------------------
set_state starting comfy-booting
COMFYUI_HOST="${COMFYUI_HOST:-127.0.0.1}"
COMFYUI_PORT="${COMFYUI_PORT:-8188}"
KITTY_WORKER_PORT="${KITTY_WORKER_PORT:-8000}"
"${PYTHON_BIN}" "${COMFYUI_ROOT}/main.py" \
  --listen "${COMFYUI_HOST}" \
  --port "${COMFYUI_PORT}" \
  --disable-auto-launch 2>&1 &
COMFY_PID=$!

COMFY_READY_TIMEOUT="${COMFY_READY_TIMEOUT_SECONDS:-600}"
COMFY_DEADLINE=$(( $(date +%s) + COMFY_READY_TIMEOUT ))
while true; do
  if ! kill -0 "${COMFY_PID}" 2>/dev/null; then
    fail "ComfyUI exited during boot (code ${COMFY_PID_RC:-unknown}); see container stderr"
  fi
  if "${PYTHON_BIN}" -c "import json,sys,urllib.request; json.load(urllib.request.urlopen('http://${COMFYUI_HOST}:${COMFYUI_PORT}/system_stats', timeout=5))" 2>/dev/null; then
    break
  fi
  if [[ "$(date +%s)" -ge "${COMFY_DEADLINE}" ]]; then
    fail "ComfyUI did not answer /system_stats within ${COMFY_READY_TIMEOUT}s"
  fi
  sleep 3
done
set_state starting comfy-ready
echo "kitty bootstrap: ComfyUI ready on ${COMFYUI_HOST}:${COMFYUI_PORT}"

# --- worker-booting -------------------------------------------------------
set_state starting worker-booting
stop_stage_server
"${PYTHON_BIN}" -m uvicorn workers.comfy_worker.app:create_app \
  --factory \
  --host 0.0.0.0 \
  --port "${KITTY_WORKER_PORT}" &
WORKER_PID=$!

KITTY_WORKER_READY_TIMEOUT="${KITTY_WORKER_READY_TIMEOUT_SECONDS:-180}"
WORKER_DEADLINE=$(( $(date +%s) + KITTY_WORKER_READY_TIMEOUT ))
WORKER_HEALTH_PAYLOAD=""
while true; do
  if ! kill -0 "${WORKER_PID}" 2>/dev/null; then
    fail "worker process exited during boot; see container stderr"
  fi
  if WORKER_HEALTH_PAYLOAD="$("${PYTHON_BIN}" -c "import json,sys,urllib.request; print(json.dumps(json.load(urllib.request.urlopen('http://127.0.0.1:${KITTY_WORKER_PORT}/health', timeout=5))))" 2>/dev/null)"; then
    break
  fi
  if [[ "$(date +%s)" -ge "${WORKER_DEADLINE}" ]]; then
    fail "worker did not answer /health within ${KITTY_WORKER_READY_TIMEOUT}s"
  fi
  sleep 2
done
set_state ready ready
echo "kitty bootstrap: worker ready; health=${WORKER_HEALTH_PAYLOAD}"
trap - EXIT
wait -n "${COMFY_PID}" "${WORKER_PID}"
wait_code=$?
set_state failed worker-exited "${wait_code}" "worker or ComfyUI exited; see container stderr"
exit "${wait_code}"
