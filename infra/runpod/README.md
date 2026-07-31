# Kitty RunPod worker

This slice creates one ephemeral GPU Pod, exposes only the authenticated Kitty worker on port `8000`, talks to ComfyUI internally on `127.0.0.1:8188`, downloads the result, records provenance and cost data, and terminates compute.

## Runtime configuration

```bash
cp infra/runpod/smoke.env.example .env.runpod.local
```

Fill the blank runtime values in `.env.runpod.local`, then load them:

```bash
set -a
source .env.runpod.local
set +a
```

The current Pod template ID is already recorded as `2lv7ev3wfp`. The template must point at an image containing the Kitty worker overlay and the configured checkpoint filename.

## Build the worker overlay

Use the exact image reference backing the verified ComfyUI template as `COMFYUI_BASE_IMAGE`:

```bash
docker build \
  --build-arg COMFYUI_BASE_IMAGE='<verified-comfyui-image:tag-or-digest>' \
  -f workers/comfy_worker/Dockerfile \
  -t '<registry>/kitty-comfy-worker:smoke' \
  .

docker push '<registry>/kitty-comfy-worker:smoke'
```

Update the private RunPod Pod template to use that image and expose HTTP port `8000` only. Do not expose `8188`, Jupyter, or SSH for this flow.

The container command is supplied by the image:

```text
/opt/kitty/start-kitty-worker.sh
```

The template must provide a ComfyUI installation at `${COMFYUI_ROOT:-/workspace/ComfyUI}` and the checkpoint named by `COMFY_CHECKPOINT`.

## Validate without spending

```bash
python scripts/runpod_worker_smoke_test.py \
  --prompt 'A cinematic portrait of an elderly carpenter in his workshop' \
  --dry-run
```

The plan is written under the ignored `data/runpod-worker-smoke/` directory. A dry run does not require live credentials.

## Run one paid smoke test

```bash
python scripts/runpod_worker_smoke_test.py \
  --prompt 'A cinematic portrait of an elderly carpenter in his workshop' \
  --accept-charges
```

Expected sequence:

```text
reconcile expired Kitty Pods
create a Pod with RunPod terminateAfter
wait for Pod RUNNING
wait for authenticated worker health
submit text_to_image_v1
poll the worker job
download and checksum the decoded image
terminate the Pod
query billing
write a unique provenance sidecar
```

The script does not retry ambiguous Pod creation or ambiguous worker submission.

## Existing managed Pod mode

Only a Pod with both the `kitty-image-` name prefix and `KITTY_MANAGED=1` marker is accepted:

```bash
python scripts/runpod_worker_smoke_test.py \
  --prompt 'A cinematic portrait of an elderly carpenter in his workshop' \
  --existing-pod-id '<pod-id>' \
  --accept-continuing-charges
```

Existing-Pod mode does not claim ownership and therefore does not terminate that Pod automatically.

## Emergency shutdown

The normal path terminates owned compute in `finally`, and RunPod also receives a cloud-side `terminateAfter` timestamp. To inspect and terminate manually, use the RunPod console's Pods page and delete any Pod whose name starts with `kitty-image-`.

Do not blindly rerun after an ambiguous creation error. Search for the exact Pod name printed by the error and remove any matching Kitty-managed Pod first.

## Focused verification

```bash
pytest -q \
  tests/test_runpod_control.py \
  tests/test_comfy_worker.py \
  tests/test_runpod_worker_smoke_test.py

ruff check \
  gateway/runpod_control.py \
  gateway/runpod_graphql.py \
  gateway/runpod_worker.py \
  workers/ \
  scripts/runpod_worker_smoke_test.py \
  tests/test_runpod_control.py \
  tests/test_comfy_worker.py \
  tests/test_runpod_worker_smoke_test.py

mypy \
  gateway/runpod_control.py \
  gateway/runpod_graphql.py \
  gateway/runpod_worker.py \
  workers/ \
  scripts/runpod_worker_smoke_test.py
```
