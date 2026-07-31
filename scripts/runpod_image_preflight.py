#!/usr/bin/env python3
"""No-GPU preflight for the immutable Kitty ComfyUI worker image.

Runs the exact GHCR image that RunPod will deploy (by digest), maps port
8000, and proves the diagnostic contract:

  * the container remains running;
  * /health becomes reachable and reports a known stage;
  * the image reaches ready (preflight mode) OR reports a structured
    failure with status/stage/exit_code/error;
  * the worker module imports and the packaged workflow files exist.

On any broken contract it exits non-zero with the structured evidence, so
the paid RunPod run is gated on this exact image having booted.

Usage:
  python scripts/runpod_image_preflight.py ghcr.io/jacob202/kitty/comfy-worker@sha256:...
"""

from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import time

HEALTH_TIMEOUT_SECONDS = 180
KNOWN_STAGES = frozenset(
    {
        "bootstrap-starting",
        "base-validating",
        "checkpoint-resolving",
        "comfy-booting",
        "comfy-ready",
        "worker-booting",
        "ready",
    }
)


def _run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    process = subprocess.run(args, capture_output=True, text=True, timeout=300)
    if check and process.returncode != 0:
        raise RuntimeError(
            f"command failed ({process.returncode}): {' '.join(args)}\n"
            f"{process.stdout}\n{process.stderr}"
        )
    return process


def _wait_health(base_url: str, timeout: int) -> tuple[int, dict]:
    import urllib.request

    deadline = time.monotonic() + timeout
    last: tuple[int, dict] = (-1, {"status": "state-missing"})
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(
                f"{base_url}/health", timeout=5
            ) as response:
                body = json.loads(response.read().decode("utf-8"))
                return response.status, body
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                last = (exc.code, json.loads(body))
            except json.JSONDecodeError:
                last = (exc.code, {"raw": body[:200]})
        except Exception:  # container still starting its port
            last = (-1, {"status": "starting", "stage": "bootstrap-starting"})
        time.sleep(3)
    return last


def _assert_ready_contract(container: str, image: str) -> None:
    base_url = "http://127.0.0.1:8000"
    status, state = _wait_health(base_url, HEALTH_TIMEOUT_SECONDS)
    if status == 200 and state.get("status") == "ready" and state.get("stage") in KNOWN_STAGES:
        print(f"PREFLIGHT_READY stage={state.get('stage')} image={image}")
        return
    print(
        f"PREFLIGHT_FAILED status={status} body={json.dumps(state)} image={image}"
    )
    logs = _run(["docker", "logs", container], check=False)
    print(f"--- container logs ---\n{logs.stdout[-4000:]}\n{logs.stderr[-4000:]}")
    raise SystemExit(1)


def _assert_failure_contract(container: str, image: str, port: int) -> None:
    base_url = f"http://127.0.0.1:{port}"
    status, state = _wait_health(base_url, 60)
    if status == 503 and state.get("status") == "failed":
        exit_code = state.get("exit_code")
        error = state.get("error")
        if exit_code is None or not error:
            print(
                f"PREFLIGHT_FAILURE_INCOMPLETE body={json.dumps(state)} image={image}"
            )
            raise SystemExit(1)
        print(
            f"PREFLIGHT_FAILURE_OK stage={state.get('stage')} exit_code={exit_code} "
            f"error={error!r} image={image}"
        )
        return
    print(
        f"PREFLIGHT_FAILURE_CONTRACT_BROKEN status={status} body={json.dumps(state)} "
        f"image={image}"
    )
    raise SystemExit(1)


def preflight(image: str) -> None:
    _run(["docker", "pull", image])

    ready_container = (
        f"kitty-preflight-{secrets.token_hex(4)}"
    )
    _run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            ready_container,
            "-p",
            "8000:8000",
            "-e",
            f"KITTY_WORKER_BEARER_TOKEN={secrets.token_hex(32)}",
            "-e",
            "KITTY_PREFLIGHT=1",
            "-e",
            "COMFY_CHECKPOINT=preflight.safetensors",
            "-e",
            f"KITTY_IMAGE_DIGEST={image.split('@sha256:', 1)[-1]}",
            image,
        ],
    )

    keeps_running = _run(
        ["docker", "inspect", "-f", "{{.State.Running}}", ready_container],
        check=False,
    )
    if keeps_running.returncode != 0 or keeps_running.stdout.strip() != "true":
        print("PREFLIGHT_FAILED container did not remain running")
        raise SystemExit(1)

    health = _run(
        [
            "docker",
            "exec",
            ready_container,
            "python3",
            "-c",
            "import json,urllib.request; print(json.load(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5))['status'])",
        ],
        check=False,
    )
    if health.returncode != 0:
        print(f"PREFLIGHT_FAILED in-container health probe: {health.stdout}{health.stderr}")
        raise SystemExit(1)
    print(f"PREFLIGHT_IN_CONTAINER_HEALTH status={health.stdout.strip()}")

    imports = _run(
        [
            "docker",
            "exec",
            ready_container,
            "python3",
            "-c",
            "import workers.comfy_worker.app; print('import-ok')",
        ],
        check=False,
    )
    if imports.returncode != 0:
        print(f"PREFLIGHT_FAILED worker import: {imports.stdout}{imports.stderr}")
        raise SystemExit(1)
    print(f"PREFLIGHT_IMPORT {imports.stdout.strip()}")

    bundle = _run(
        [
            "docker",
            "exec",
            ready_container,
            "sh",
            "-c",
            "ls -1 /opt/kitty/workflows/*/workflow-api.json /opt/kitty/workflows/*/manifest.yaml",
        ],
        check=False,
    )
    if bundle.returncode != 0:
        print(f"PREFLIGHT_FAILED workflow bundle missing:\n{bundle.stderr}")
        raise SystemExit(1)
    print(f"PREFLIGHT_BUNDLE\n{bundle.stdout.strip()}")

    try:
        _assert_ready_contract(ready_container, image)
    finally:
        _run(["docker", "rm", "-f", ready_container], check=False)

    failure_container = f"kitty-preflight-fail-{secrets.token_hex(4)}"
    _run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            failure_container,
            "-p",
            "8001:8000",
            "-e",
            "KITTY_WORKER_BEARER_TOKEN=",
            "-e",
            "KITTY_PREFLIGHT=1",
            "-e",
            "COMFY_CHECKPOINT=preflight.safetensors",
            "-e",
            f"KITTY_IMAGE_DIGEST={image.split('@sha256:', 1)[-1]}",
            image,
        ],
    )
    try:
        _assert_failure_contract(failure_container, image, port=8001)
    finally:
        _run(["docker", "rm", "-f", failure_container], check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", help="ghcr.io/jacob202/kitty/comfy-worker@sha256:...")
    args = parser.parse_args()
    try:
        preflight(args.image)
    except Exception as exc:
        print(f"PREFLIGHT_ERROR {exc}")
        return 1
    print("PREFLIGHT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
