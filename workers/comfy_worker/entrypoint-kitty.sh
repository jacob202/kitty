#!/usr/bin/env bash
set -euo pipefail

# PID 1 of the Kitty worker image.
#
# Order matters: the diagnostic server binds the worker port BEFORE any
# dependency, model, or ComfyUI discovery work, and it is supervised from
# here so that a dead bootstrap still leaves a queryable /health endpoint.
# The stage state is written to a JSON file that the server reflects, so
# callers can always read: status, stage, exit_code, error, timestamp, digest.

export KITTY_STATE_FILE="${KITTY_STATE_FILE:-/tmp/kitty-state.json}"
export KITTY_STAGE_PIDFILE="${KITTY_STAGE_PIDFILE:-/tmp/kitty-stage.pid}"
export KITTY_WORKER_PORT="${KITTY_WORKER_PORT:-8000}"
export KITTY_IMAGE_DIGEST="${KITTY_IMAGE_DIGEST:-unknown}"
export KITTY_STAGE_SERVER_PY="${KITTY_STAGE_SERVER_PY:-/tmp/kitty-stage-server.py}"
BOOTSTRAP_PID=""

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
    os.makedirs(os.path.dirname(os.environ["KITTY_STATE_FILE"]) or ".", exist_ok=True)
    with open(os.environ["KITTY_STATE_FILE"], "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload))
except OSError:
    pass
PY
}

state_field() {
  local field="$1"
  python3 - "$KITTY_STATE_FILE" "$field" <<'PY' 2>/dev/null || true
import json
import sys

try:
    value = json.load(open(sys.argv[1], encoding="utf-8")).get(sys.argv[2], "")
except (OSError, json.JSONDecodeError):
    value = ""
print(value)
PY
}

stage_server_running() {
  [[ -f "${KITTY_STAGE_PIDFILE}" ]] || return 1
  kill -0 "$(cat "${KITTY_STAGE_PIDFILE}")" 2>/dev/null
}

start_stage_server() {
  cat > "${KITTY_STAGE_SERVER_PY}" <<'PY'
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Server(ThreadingHTTPServer):
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        state_file = Path(os.environ["KITTY_STATE_FILE"])
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {"status": "starting", "stage": "state-missing"}
        ready = state.get("status") == "ready"
        payload = json.dumps(state).encode("utf-8")
        path = self.path.split("?", 1)[0]
        if ready and path == "/health":
            self.send_response(200)
        elif path == "/health":
            self.send_response(503)
        else:
            self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, _format: str, *_args: object) -> None:
        return


Server(("0.0.0.0", int(os.environ["KITTY_WORKER_PORT"])), Handler).serve_forever()
PY
  rm -f "${KITTY_STAGE_PIDFILE}"
  KITTY_STATE_FILE="${KITTY_STATE_FILE}" \
    KITTY_WORKER_PORT="${KITTY_WORKER_PORT}" \
    python3 -u "${KITTY_STAGE_SERVER_PY}" &
  echo $! > "${KITTY_STAGE_PIDFILE}"
  sleep 1
  if ! stage_server_running; then
    echo "kitty entrypoint: unable to bind diagnostic server on port ${KITTY_WORKER_PORT}" >&2
    exit 2
  fi
}

stop_stage_server() {
  if [[ -f "${KITTY_STAGE_PIDFILE}" ]]; then
    kill "$(cat "${KITTY_STAGE_PIDFILE}")" 2>/dev/null || true
    wait "$(cat "${KITTY_STAGE_PIDFILE}")" 2>/dev/null || true
    rm -f "${KITTY_STAGE_PIDFILE}"
  fi
}

shutdown() {
  if [[ -n "${BOOTSTRAP_PID}" ]]; then
    kill "${BOOTSTRAP_PID}" 2>/dev/null || true
    wait "${BOOTSTRAP_PID}" 2>/dev/null || true
    BOOTSTRAP_PID=""
  fi
  stop_stage_server
  exit 0
}
trap shutdown TERM INT

set_state starting bootstrap-starting
start_stage_server

# Run bootstrap as a supervised child. `wait` is interruptible, so PID 1 can
# handle TERM immediately; running the child in the foreground previously
# delayed traps and made Docker fall back to SIGKILL.
if [[ $# -gt 0 ]]; then
  "$@" &
else
  /opt/kitty/bootstrap.sh &
fi
BOOTSTRAP_PID=$!
set +e
wait "${BOOTSTRAP_PID}"
bootstrap_rc=$?
set -e
BOOTSTRAP_PID=""

if [[ ${bootstrap_rc} -ne 0 ]]; then
  last_stage="$(state_field stage)"
  [[ -n "${last_stage}" ]] || last_stage="unknown"
  # bootstrap.sh records the precise failing stage and message. Preserve it;
  # only synthesize a generic state for commands that exited without one.
  if [[ "$(state_field status)" != "failed" ]]; then
    set_state failed "${last_stage}" "${bootstrap_rc}" "bootstrap exited non-zero (see container stderr)"
  fi
  if ! stage_server_running; then
    start_stage_server
  fi
  echo "kitty entrypoint: bootstrap failed stage=${last_stage} exit=${bootstrap_rc}; keeping diagnostic server alive" >&2
  while stage_server_running; do
    set +e
    wait "$(cat "${KITTY_STAGE_PIDFILE}")"
    set -e
  done
  exit 1
fi

# In normal operation bootstrap owns ComfyUI and the worker until either exits.
# Reaching here means that pair exited cleanly; release the diagnostic port.
stop_stage_server
exit 0
