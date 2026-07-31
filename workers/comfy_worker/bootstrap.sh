#!/usr/bin/env bash
set -euo pipefail

: "${KITTY_WORKER_BEARER_TOKEN:?KITTY_WORKER_BEARER_TOKEN is required}"
: "${KITTY_BOOTSTRAP_REF:?KITTY_BOOTSTRAP_REF is required}"
: "${COMFY_CHECKPOINT:?COMFY_CHECKPOINT is required}"
: "${COMFY_CHECKPOINT_URL:?COMFY_CHECKPOINT_URL is required}"

PYTHON_BIN="${COMFYUI_PYTHON:-python}"
SOURCE_ROOT="/opt/kitty-src"
ARCHIVE_PATH="/tmp/kitty-src.tar.gz"
STAGE_FILE="/tmp/kitty-bootstrap-stage"
BOOTSTRAP_HEALTH_PID=""

set_stage() {
  printf '%s\n' "$1" > "${STAGE_FILE}"
  printf 'kitty bootstrap: %s\n' "$1"
}

stop_bootstrap_health() {
  if [[ -n "${BOOTSTRAP_HEALTH_PID}" ]]; then
    kill "${BOOTSTRAP_HEALTH_PID}" 2>/dev/null || true
    wait "${BOOTSTRAP_HEALTH_PID}" 2>/dev/null || true
    BOOTSTRAP_HEALTH_PID=""
  fi
}

trap stop_bootstrap_health EXIT INT TERM
set_stage "starting-bootstrap-health"

STAGE_FILE="${STAGE_FILE}" KITTY_WORKER_PORT="${KITTY_WORKER_PORT:-8000}" \
  "${PYTHON_BIN}" -u - <<'PY' &
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

stage_file = Path(os.environ["STAGE_FILE"])
port = int(os.environ["KITTY_WORKER_PORT"])


class Server(ThreadingHTTPServer):
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        stage = (
            stage_file.read_text(encoding="utf-8").strip()
            if stage_file.exists()
            else "starting"
        )
        payload = json.dumps({"status": "starting", "stage": stage}).encode("utf-8")
        path = self.path.split("?", 1)[0]
        self.send_response(503 if path == "/health" else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, _format: str, *_args: object) -> None:
        return


Server(("0.0.0.0", port), Handler).serve_forever()
PY
BOOTSTRAP_HEALTH_PID=$!
sleep 1
if ! kill -0 "${BOOTSTRAP_HEALTH_PID}" 2>/dev/null; then
  echo "Unable to bind bootstrap health server on port ${KITTY_WORKER_PORT:-8000}" >&2
  wait "${BOOTSTRAP_HEALTH_PID}" || true
  exit 2
fi

set_stage "downloading-kitty-source"
"${PYTHON_BIN}" - <<'PY'
import os
import pathlib
import time
import urllib.request

ref = os.environ["KITTY_BOOTSTRAP_REF"]
source_root = pathlib.Path("/opt/kitty-src")
if source_root.exists():
    import shutil
    shutil.rmtree(source_root)
source_root.mkdir(parents=True, exist_ok=True)

base = f"https://raw.githubusercontent.com/jacob202/kitty/{ref}"
files = [
    "workers/comfy_worker/app.py",
    "workers/comfy_worker/start.sh",
    "workers/comfy_worker/requirements.txt",
    "workflows/text_to_image_v1/workflow-api.json",
    "workflows/text_to_image_v1/manifest.yaml",
]
agent = "Kitty-Image-Studio/1.0"

for rel_path in files:
    target = source_root / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    url = f"{base}/{rel_path}"
    req = urllib.request.Request(url, headers={"User-Agent": agent})
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp, target.open("wb") as f:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
            break
        except Exception as exc:
            if attempt == 3:
                raise SystemExit(f"download {rel_path} failed: {exc}") from exc
            time.sleep(min(attempt * 5, 15))
PY

set_stage "installing-worker-dependencies"
"${PYTHON_BIN}" -m pip install --no-cache-dir -r "${SOURCE_ROOT}/workers/comfy_worker/requirements.txt"

set_stage "locating-comfyui"
COMFYUI_ROOT="${COMFYUI_ROOT:-/workspace/ComfyUI}"
if [[ ! -f "${COMFYUI_ROOT}/main.py" ]]; then
  DISCOVERED_MAIN="$(find /workspace /opt /app -type f -path '*/ComfyUI/main.py' -print -quit 2>/dev/null || true)"
  if [[ -z "${DISCOVERED_MAIN}" ]]; then
    echo "Unable to locate ComfyUI/main.py" >&2
    exit 2
  fi
  COMFYUI_ROOT="$(dirname "${DISCOVERED_MAIN}")"
fi
export COMFYUI_ROOT

CHECKPOINT_DIR="${COMFYUI_ROOT}/models/checkpoints"
CHECKPOINT_PATH="${CHECKPOINT_DIR}/${COMFY_CHECKPOINT}"
mkdir -p "${CHECKPOINT_DIR}" /workspace/jobs

if [[ ! -s "${CHECKPOINT_PATH}" ]]; then
  set_stage "downloading-checkpoint"
  export CHECKPOINT_PATH
  "${PYTHON_BIN}" - <<'PY'
import hashlib
import os
import pathlib
import urllib.request

url = os.environ["COMFY_CHECKPOINT_URL"]
target = pathlib.Path(os.environ["CHECKPOINT_PATH"])
partial = target.with_suffix(target.suffix + ".part")
expected = os.environ.get("COMFY_CHECKPOINT_SHA256", "").strip().lower()
request = urllib.request.Request(url, headers={"User-Agent": "Kitty-Image-Studio/1.0"})
with urllib.request.urlopen(request, timeout=300) as response, partial.open("wb") as output:
    while True:
        chunk = response.read(8 * 1024 * 1024)
        if not chunk:
            break
        output.write(chunk)
if partial.stat().st_size < 1024 * 1024:
    raise SystemExit("checkpoint download was unexpectedly small")
if expected:
    digest = hashlib.sha256()
    with partial.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest().lower() != expected:
        raise SystemExit("checkpoint SHA-256 mismatch")
partial.replace(target)
PY
else
  set_stage "checkpoint-already-present"
fi

export PYTHONPATH="${SOURCE_ROOT}"
export COMFY_URL="http://127.0.0.1:8188"
export KITTY_WORKFLOW_ROOT="${SOURCE_ROOT}/workflows"
export KITTY_JOB_ROOT="/workspace/jobs"
export KITTY_ALLOWED_CHECKPOINTS="${COMFY_CHECKPOINT}"
export KITTY_WORKER_PORT="${KITTY_WORKER_PORT:-8000}"

set_stage "starting-kitty-worker"
stop_bootstrap_health
trap - EXIT INT TERM
exec "${SOURCE_ROOT}/workers/comfy_worker/start.sh"
