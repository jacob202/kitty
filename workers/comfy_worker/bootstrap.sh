#!/usr/bin/env bash
set -euo pipefail

: "${KITTY_WORKER_BEARER_TOKEN:?KITTY_WORKER_BEARER_TOKEN is required}"
: "${KITTY_BOOTSTRAP_REF:?KITTY_BOOTSTRAP_REF is required}"
: "${COMFY_CHECKPOINT:?COMFY_CHECKPOINT is required}"
: "${COMFY_CHECKPOINT_URL:?COMFY_CHECKPOINT_URL is required}"

PYTHON_BIN="${COMFYUI_PYTHON:-python}"
SOURCE_ROOT="/opt/kitty-src"
ARCHIVE_PATH="/tmp/kitty-src.tar.gz"

"${PYTHON_BIN}" - <<'PY'
import os
import pathlib
import tarfile
import urllib.request

ref = os.environ["KITTY_BOOTSTRAP_REF"]
archive = pathlib.Path("/tmp/kitty-src.tar.gz")
url = f"https://github.com/jacob202/kitty/archive/{ref}.tar.gz"
with urllib.request.urlopen(url, timeout=120) as response, archive.open("wb") as target:
    while True:
        chunk = response.read(1024 * 1024)
        if not chunk:
            break
        target.write(chunk)

extract_root = pathlib.Path("/opt/kitty-extract")
extract_root.mkdir(parents=True, exist_ok=True)
with tarfile.open(archive, "r:gz") as bundle:
    bundle.extractall(extract_root)
children = [item for item in extract_root.iterdir() if item.is_dir()]
if len(children) != 1:
    raise SystemExit(f"unexpected Kitty archive layout: {children}")
source = children[0]
destination = pathlib.Path("/opt/kitty-src")
if destination.exists():
    import shutil
    shutil.rmtree(destination)
source.rename(destination)
PY

"${PYTHON_BIN}" -m pip install --no-cache-dir -r "${SOURCE_ROOT}/workers/comfy_worker/requirements.txt"

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
fi

export PYTHONPATH="${SOURCE_ROOT}"
export COMFY_URL="http://127.0.0.1:8188"
export KITTY_WORKFLOW_ROOT="${SOURCE_ROOT}/workflows"
export KITTY_JOB_ROOT="/workspace/jobs"
export KITTY_ALLOWED_CHECKPOINTS="${COMFY_CHECKPOINT}"
export KITTY_WORKER_PORT="${KITTY_WORKER_PORT:-8000}"

exec "${SOURCE_ROOT}/workers/comfy_worker/start.sh"
