#!/usr/bin/env bash
set -Eeuo pipefail

LOG="/workspace/kitty-live-$(date +%Y%m%d-%H%M%S).log"
BOOT_LOG="/workspace/kitty-patched-bootstrap.log"
STATE_FILE="/tmp/kitty-live-state.json"
STAGE_PIDFILE="/tmp/kitty-live-stage.pid"
PATCH_DIR="/tmp/kitty-livefix"
PATCH_COMMIT="8659dee5a5764e9b8d57624efa2ffe9e646abce0"

mkdir -p /workspace "$PATCH_DIR"
exec > >(tee "$LOG") 2>&1

fail_report() {
  rc=$?
  echo
  echo "=== LIVE TEST FAILED rc=${rc} ==="
  echo "State:"
  cat "$STATE_FILE" 2>/dev/null || echo "No live state file"
  echo
  echo "Bootstrap tail:"
  tail -n 250 "$BOOT_LOG" 2>/dev/null || echo "No bootstrap log"
  echo
  echo "Listening ports:"
  ss -lntp 2>/dev/null || netstat -lntp 2>/dev/null || true
  echo
  echo "Full log: $LOG"
  exit "$rc"
}
trap fail_report ERR

echo "=== KITTY LIVE RUNPOD TEST $(date -Is) ==="
echo "Host: $(hostname)"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>&1 || true

echo
echo "=== EXISTING RUNTIME ==="
ps auxww | grep -E 'ComfyUI|comfyui|uvicorn|kitty' | grep -v grep || true
ss -lntp 2>/dev/null || netstat -lntp 2>/dev/null || true

echo
echo "=== DISCOVERY ==="
for candidate in /opt/comfyui-baked /workspace/ComfyUI /workspace/comfyui /opt/ComfyUI /app/ComfyUI /app/comfyui; do
  [[ -f "$candidate/main.py" ]] && echo "ComfyUI: $candidate"
done
[[ -d /opt/kitty ]] && echo "Kitty source: /opt/kitty" || { echo "FATAL: /opt/kitty is absent; this pod is not running the Kitty worker image"; exit 10; }
[[ -f /opt/kitty/workers/comfy_worker/app.py ]] || { echo "FATAL: Kitty worker app is absent from /opt/kitty"; exit 11; }

python3 - "$PATCH_DIR" "$PATCH_COMMIT" <<'PY'
import pathlib
import sys
import urllib.request

target = pathlib.Path(sys.argv[1])
commit = sys.argv[2]
base = f"https://raw.githubusercontent.com/jacob202/kitty/{commit}"
for path in (
    "workers/comfy_worker/bootstrap.sh",
    "workers/comfy_worker/entrypoint-kitty.sh",
):
    destination = target / pathlib.Path(path).name
    url = f"{base}/{path}"
    print(f"Downloading {url}", flush=True)
    urllib.request.urlretrieve(url, destination)
    destination.chmod(0o755)
PY

export PYTHONPATH="/opt/kitty${PYTHONPATH:+:$PYTHONPATH}"
export COMFYUI_ROOT="${COMFYUI_ROOT:-/opt/comfyui-baked}"
export COMFYUI_PYTHON="${COMFYUI_PYTHON:-python3}"
export COMFYUI_HOST="127.0.0.1"
export COMFYUI_PORT="8189"
export COMFY_URL="http://127.0.0.1:8189"
export KITTY_WORKER_PORT="8001"
export KITTY_STATE_FILE="$STATE_FILE"
export KITTY_STAGE_PIDFILE="$STAGE_PIDFILE"
export KITTY_STAGE_SERVER_PY="/tmp/kitty-live-stage-server.py"
export KITTY_JOB_ROOT="/workspace/kitty-live-jobs"
export KITTY_MODEL_CACHE_DIR="/workspace/kitty-models"
export COMFY_CHECKPOINT="RealVisXL_V4.0.safetensors"
export KITTY_ALLOWED_CHECKPOINTS="$COMFY_CHECKPOINT"
export COMFY_CHECKPOINT_URL="https://huggingface.co/SG161222/RealVisXL_V4.0/resolve/main/RealVisXL_V4.0.safetensors?download=true"
export COMFY_CHECKPOINT_SHA256="912c9dc74f5855175c31a7993f863a043ac8dcc31732b324cd05d75cd7e16844"
export COMFY_READY_TIMEOUT_SECONDS="900"
export KITTY_WORKER_READY_TIMEOUT_SECONDS="180"

if [[ -z "${KITTY_WORKER_BEARER_TOKEN:-}" ]]; then
  KITTY_WORKER_BEARER_TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  export KITTY_WORKER_BEARER_TOKEN
fi

# Clean only earlier isolated live-test processes; leave the pod's normal services alone.
if [[ -f "$STAGE_PIDFILE" ]]; then
  kill "$(cat "$STAGE_PIDFILE")" 2>/dev/null || true
  rm -f "$STAGE_PIDFILE"
fi
pkill -f 'workers.comfy_worker.app:create_app.*--port 8001' 2>/dev/null || true
pkill -f 'main.py.*--port 8189' 2>/dev/null || true
rm -f "$STATE_FILE"

echo
echo "=== STARTING PATCHED WORKER ON LOCAL PORTS 8001/8189 ==="
cd /opt/kitty
"$PATCH_DIR/entrypoint-kitty.sh" "$PATCH_DIR/bootstrap.sh" >"$BOOT_LOG" 2>&1 &
PATCH_PID=$!
echo "Patched supervisor PID: $PATCH_PID"

echo
echo "=== HEALTH TRANSITIONS ==="
python3 - <<'PY'
import json
import os
import time
import urllib.error
import urllib.request

url = "http://127.0.0.1:8001/health"
deadline = time.time() + 1200
previous = None
while time.time() < deadline:
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            body = response.read().decode("utf-8", errors="replace")
            current = f"{response.status}:{body}"
            if current != previous:
                print(current, flush=True)
                previous = current
            payload = json.loads(body)
            if payload.get("status") == "ok":
                raise SystemExit(0)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        current = f"{exc.code}:{body}"
        if current != previous:
            print(current, flush=True)
            previous = current
    except Exception as exc:
        current = f"unavailable:{exc!r}"
        if current != previous:
            print(current, flush=True)
            previous = current
    time.sleep(3)
raise SystemExit("worker did not become healthy within 1200 seconds")
PY

echo
echo "=== SUBMITTING ONE REAL JAMES IMAGE ==="
python3 - <<'PY'
import hashlib
import json
import os
import time
import urllib.request

base = "http://127.0.0.1:8001"
token = os.environ["KITTY_WORKER_BEARER_TOKEN"]
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
payload = {
    "workflow_id": "text_to_image_v1",
    "prompt": "A candid recent iPhone photograph of James, a heavyset Canadian man in his late thirties, approximately 240 pounds, broad friendly face, short dark brown hair with natural greying at the temples, kind blue eyes, relaxed genuine smile, broad shoulders, casual dark navy cotton T-shirt, seated near a window in an ordinary lived-in room, realistic skin pores and natural facial asymmetry, believable body proportions, subtle phone-camera noise, unposed documentary realism, no retouching",
    "negative_prompt": "illustration, painting, CGI, plastic skin, beauty retouching, glamour, young skinny man, bodybuilder, exaggerated muscles, distorted face, deformed eyes, extra fingers, watermark, text, logo",
    "checkpoint": "RealVisXL_V4.0.safetensors",
    "width": 1024,
    "height": 1024,
    "steps": 24,
    "guidance": 5.0,
    "seed": 38472619,
    "count": 1,
    "client_action_id": f"james-live-proof-{int(time.time())}",
}
request = urllib.request.Request(f"{base}/v1/jobs", data=json.dumps(payload).encode(), headers=headers, method="POST")
with urllib.request.urlopen(request, timeout=30) as response:
    job = json.load(response)
job_id = job["job_id"]
print(f"Job accepted: {job_id}", flush=True)
last = None
deadline = time.time() + 900
while time.time() < deadline:
    request = urllib.request.Request(f"{base}/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=30) as response:
        job = json.load(response)
    current = (job.get("status"), job.get("error"))
    if current != last:
        print(f"status={current[0]} error={current[1]}", flush=True)
        last = current
    if job.get("status") == "succeeded":
        output = job["outputs"][0]
        request = urllib.request.Request(f"{base}{output['download_url']}", headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(request, timeout=120) as response:
            image = response.read()
        destination = "/workspace/james-live.png"
        pathlib = __import__("pathlib")
        pathlib.Path(destination).write_bytes(image)
        print("GENERATION_SUCCEEDED", flush=True)
        print(f"IMAGE={destination}", flush=True)
        print(f"SIZE={len(image)}", flush=True)
        print(f"SHA256={hashlib.sha256(image).hexdigest()}", flush=True)
        raise SystemExit(0)
    if job.get("status") in {"failed", "cancelled"}:
        print(json.dumps(job, indent=2), flush=True)
        raise SystemExit(1)
    time.sleep(3)
raise SystemExit("generation timed out")
PY

trap - ERR
echo
echo "=== SUCCESS ==="
echo "Image: /workspace/james-live.png"
echo "Bootstrap log: $BOOT_LOG"
echo "Full diagnostic log: $LOG"
