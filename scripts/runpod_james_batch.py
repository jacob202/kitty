#!/usr/bin/env python3
"""Run several James portrait prompts through one guarded Kitty RunPod session."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import math
import os
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import httpx
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateway.runpod_control import PodInfo, RunPodControlClient, RunPodError  # noqa: E402
from gateway.runpod_worker import (  # noqa: E402
    RunPodWorkerClient,
    RunPodWorkerError,
    RunPodWorkerNotListeningError,
)

WORKER_PORT = 8000
# Long enough for RunPod to schedule the container and for bootstrap.sh to
# bind its stage server; short enough that a dead start command costs
# seconds of GPU rather than the full readiness timeout.
NOT_LISTENING_GRACE_SECONDS = 180
WORKFLOW_ID = "text_to_image_v1"

DEFAULT_PROMPTS = (
    "A candid recent iPhone photo of James, a heavyset Canadian man in his late thirties, around 240 pounds, broad friendly face, short dark brown hair with visible natural greying at the temples, relaxed warm smile, casual navy cotton T-shirt, seated near a window, realistic skin texture, subtle phone-camera noise, natural color, ordinary lived-in room, chest-up portrait, unposed, no glamour retouching",
    "A realistic recent iPhone snapshot of James outdoors in Saskatchewan at golden hour, a heavyset man in his late thirties around 240 pounds, short dark hair with noticeable grey at the temples, kind eyes, slightly shy genuine smile, casual charcoal hoodie and jeans, natural body proportions, standing beside a wooden fence, soft prairie background, authentic skin texture, candid composition, modern phone camera color",
    "A casual iPhone photo of James laughing in a kitchen while making coffee, heavyset adult man in his late thirties around 240 pounds, short dark brown hair greying naturally, broad shoulders, warm approachable expression, grey henley shirt, realistic hands, ordinary kitchen lighting, slight motion blur, believable phone-camera exposure, documentary realism, not posed",
    "A full-body recent iPhone photo of James walking through a quiet city park, heavyset adult man in his late thirties around 240 pounds, short dark hair with visible greying, casual plaid overshirt over a black T-shirt, jeans and sneakers, relaxed posture, natural smile, overcast daylight, authentic proportions, realistic skin and fabric, ordinary candid photography",
    "A close realistic iPhone portrait of James on a couch after a long day, heavyset adult man in his late thirties, short dark brown hair with distinct grey at the temples, soft tired but happy expression, warm lamp light mixed with cool window light, casual black T-shirt, natural pores and facial asymmetry, subtle phone sharpening, intimate candid photograph",
    "A cheerful recent iPhone photo of James at a casual backyard barbecue, heavyset Canadian man in his late thirties around 240 pounds, short dark hair greying at the temples, broad genuine smile, dark green polo shirt, holding a paper plate, friends softly out of focus behind him, summer evening light, realistic body proportions, natural color, candid social snapshot",
)

NEGATIVE_PROMPT = (
    "illustration, painting, CGI, plastic skin, beauty retouching, model pose, "
    "young skinny man, bodybuilder, exaggerated muscles, duplicated person, extra fingers, "
    "bad hands, deformed eyes, asymmetrical eyes, distorted face, watermark, text, logo"
)


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    value = float(raw)
    if not math.isfinite(value):
        raise RuntimeError(f"{name} must be finite")
    return value


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else default


_RUNTIME_EVIDENCE_KEYS = frozenset(
    {
        "id",
        "name",
        "desiredStatus",
        "lastStatusChange",
        "imageName",
        "dockerId",
        "containerDiskInGb",
        "volumeInGb",
        "volumeMountPath",
        "gpuCount",
        "machineId",
        "podType",
        "port",
        "ports",
    }
)


def _runtime_evidence(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Subset of the raw Pod resource safe to record: no env values, no keys
    that may carry secrets. Env is reduced to key names only — the worker
    bearer token lives in env, and RunPod pod logs are public in this repo."""
    evidence = {
        str(key): payload[key]
        for key in _RUNTIME_EVIDENCE_KEYS
        if key in payload
    }
    env = payload.get("env")
    if isinstance(env, list):
        evidence["env_keys"] = [
            str(item.get("key"))
            for item in env
            if isinstance(item, Mapping) and item.get("key")
        ]
    runtime = payload.get("runtime")
    if isinstance(runtime, Mapping):
        ports = runtime.get("ports")
        if isinstance(ports, list):
            evidence["runtime_ports"] = [
                {k: v for k, v in item.items() if k in {"publicPort", "privatePort", "type"}}
                for item in ports
                if isinstance(item, Mapping)
            ]
    return evidence


async def _wait_for_pod(
    client: RunPodControlClient,
    pod_id: str,
    *,
    timeout_seconds: int,
    poll_seconds: float,
) -> tuple[PodInfo, list[dict[str, Any]], dict[str, Any]]:
    deadline = time.monotonic() + timeout_seconds
    transitions: list[dict[str, Any]] = []
    runtime_config: dict[str, Any] = {}
    pod: PodInfo | None = None
    while time.monotonic() < deadline:
        pod = await client.get_pod(pod_id)
        if pod.desired_status != (transitions[-1]["desired_status"] if transitions else None):
            transitions.append(
                {
                    "desired_status": pod.desired_status,
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        if pod.desired_status == "RUNNING":
            raw = await client.get_pod_raw(pod_id)
            runtime_config = _runtime_evidence(raw)
            return pod, transitions, runtime_config
        if pod.desired_status in {"EXITED", "TERMINATED"}:
            raw = await client.get_pod_raw(pod_id)
            runtime_config = _runtime_evidence(raw)
            raise RuntimeError(
                f"Pod entered terminal state {pod.desired_status}; "
                f"transitions={transitions}; runtime={runtime_config}"
            )
        await asyncio.sleep(poll_seconds)
    raise RuntimeError(
        "Pod readiness timeout; transitions="
        f"{transitions}; last status={pod.desired_status if pod else 'never-seen'}"
    )


async def _wait_for_worker(
    client: RunPodWorkerClient,
    *,
    timeout_seconds: int,
    poll_seconds: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    deadline = time.monotonic() + timeout_seconds
    # A 404 is survivable only while the container is still being scheduled and
    # the start command has not yet bound the port. Past this grace window it
    # means the start command never ran, and waiting out the full timeout just
    # bills GPU time for an answer we already have.
    not_listening_grace = time.monotonic() + NOT_LISTENING_GRACE_SECONDS
    last_error = "not contacted"
    health_stage_history: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        status_code, body = await client.read_health()
        if status_code > 0 and body is not None:
            sample = {
                "status_code": status_code,
                "status": body.get("status"),
                "stage": body.get("stage"),
                "exit_code": body.get("exit_code"),
                "error": body.get("error"),
            }
            if not health_stage_history or health_stage_history[-1] != sample:
                health_stage_history.append(sample)
        try:
            ready = await client.assert_ready()
            await client.read_health()  # capture the final ready body
            status_code, body = await client.read_health()
            if body is not None:
                sample = {
                    "status_code": status_code,
                    "status": body.get("status"),
                    "stage": body.get("stage"),
                }
                if not health_stage_history or health_stage_history[-1] != sample:
                    health_stage_history.append(sample)
            return ready, health_stage_history
        except RunPodWorkerNotListeningError as exc:
            last_error = str(exc)
            if time.monotonic() > not_listening_grace:
                raise RuntimeError(
                    "worker never bound its port: "
                    f"{NOT_LISTENING_GRACE_SECONDS}s of 404 responses. The "
                    "container start command did not run, so readiness will "
                    f"never arrive. stage_history={health_stage_history} {last_error}"
                ) from exc
            await asyncio.sleep(poll_seconds)
        except (httpx.HTTPError, RunPodWorkerError) as exc:
            # 503 from the bootstrap stage server or the worker itself means
            # progress is being made — keep waiting for the full timeout.
            last_error = str(exc)
            await asyncio.sleep(poll_seconds)
    raise RuntimeError(
        f"worker readiness timeout: {last_error} "
        f"stage_history={health_stage_history}"
    )


def _validate_image(data: bytes, expected_sha256: str) -> tuple[int, int, str]:
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 and digest != expected_sha256:
        raise RuntimeError("downloaded image checksum did not match worker provenance")
    with Image.open(io.BytesIO(data)) as image:
        image.verify()
    with Image.open(io.BytesIO(data)) as image:
        width, height = image.size
        image_format = str(image.format or "").lower()
    if image_format not in {"png", "jpeg", "webp"}:
        raise RuntimeError(f"unexpected generated image format: {image_format}")
    return width, height, digest


async def run(args: argparse.Namespace) -> Path:
    api_key = _required_env("RUNPOD_API_KEY")
    worker_image = _required_env("KITTY_WORKER_IMAGE")
    if "@sha256:" not in worker_image or not worker_image.startswith(("ghcr.io/", "docker.io/")):
        raise RuntimeError(
            "KITTY_WORKER_IMAGE must be an immutable digest reference, "
            "e.g. ghcr.io/jacob202/kitty/comfy-worker@sha256:..."
        )
    worker_token = _required_env("KITTY_WORKER_BEARER_TOKEN")
    if len(worker_token) < 32:
        raise RuntimeError("KITTY_WORKER_BEARER_TOKEN must contain at least 32 characters")

    checkpoint = os.environ.get("COMFY_CHECKPOINT", "RealVisXL_V4.0.safetensors")
    checkpoint_url = os.environ.get(
        "COMFY_CHECKPOINT_URL",
        "https://huggingface.co/SG161222/RealVisXL_V4.0/resolve/main/RealVisXL_V4.0.safetensors?download=true",
    )
    checkpoint_sha = os.environ.get(
        "COMFY_CHECKPOINT_SHA256",
        "912c9dc74f5855175c31a7993f863a043ac8dcc31732b324cd05d75cd7e16844",
    )
    max_hourly_rate = _float_env("RUNPOD_MAX_HOURLY_RATE", 0.60)
    hard_runtime_minutes = _int_env("RUNPOD_HARD_RUNTIME_MINUTES", 120)
    ready_timeout = _int_env("RUNPOD_READY_TIMEOUT_SECONDS", 1200)
    generation_timeout = _int_env("RUNPOD_GENERATION_TIMEOUT_SECONDS", 600)
    poll_seconds = _float_env("RUNPOD_POLL_INTERVAL_SECONDS", 5.0)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    prompts = DEFAULT_PROMPTS[: args.attempts]
    if not prompts:
        raise RuntimeError("attempts must be at least 1")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)
    pod: PodInfo | None = None
    pod_transitions: list[dict[str, Any]] = []
    pod_runtime: dict[str, Any] = {}
    health_stage_history: list[dict[str, Any]] = []
    billing_records: list[dict[str, Any]] = []
    billing_errors: list[str] = []
    started = time.monotonic()
    records: list[dict[str, Any]] = []
    cleanup_errors: list[str] = []
    failure: Exception | None = None

    async with httpx.AsyncClient() as http_client:
        try:
            async with RunPodControlClient(api_key) as runpod:
                pod = await runpod.create_image_pod(
                    template_id="",
                    gpu_type_ids=(
                        "NVIDIA GeForce RTX 3090",
                        "NVIDIA RTX A5000",
                        "NVIDIA GeForce RTX 4090",
                    ),
                    max_hourly_rate=max_hourly_rate,
                    hard_runtime_minutes=hard_runtime_minutes,
                    ports=("8000/http", "8188/http"),
                    cloud_type=os.environ.get("RUNPOD_CLOUD_TYPE", "COMMUNITY"),
                    container_disk_gb=50,
                    volume_gb=20,
                    env={
                        "KITTY_WORKER_BEARER_TOKEN": worker_token,
                        "COMFY_CHECKPOINT": checkpoint,
                        "COMFY_CHECKPOINT_URL": checkpoint_url,
                        "COMFY_CHECKPOINT_SHA256": checkpoint_sha,
                        "KITTY_ALLOWED_CHECKPOINTS": checkpoint,
                        "COMFYUI_PYTHON": "python3",
                    },
                    name_suffix=f"james-{run_id}",
                    image_name=worker_image,
                )
                pod, pod_transitions, pod_runtime = await _wait_for_pod(
                    runpod,
                    pod.pod_id,
                    timeout_seconds=ready_timeout,
                    poll_seconds=poll_seconds,
                )
                comfy_url = pod.proxy_url(8188)
                try:
                    comfy_resp = await http_client.get(f"{comfy_url}/", timeout=10)
                    print(
                        f"comfy-proxy 8188 status={comfy_resp.status_code} "
                        f"len={len(comfy_resp.text)}",
                        flush=True,
                    )
                except Exception as exc:
                    print(f"comfy-proxy 8188 unreachable: {exc}", flush=True)
                worker_url = pod.proxy_url(WORKER_PORT)
                async with RunPodWorkerClient(worker_url, worker_token) as worker:
                    health, stage_history = await _wait_for_worker(
                        worker,
                        timeout_seconds=ready_timeout,
                        poll_seconds=poll_seconds,
                    )
                    health_stage_history = stage_history
                    for index, prompt in enumerate(prompts, start=1):
                        seed = secrets.randbits(63)
                        submitted = await worker.submit(
                            workflow_id=WORKFLOW_ID,
                            prompt=prompt,
                            negative_prompt=NEGATIVE_PROMPT,
                            checkpoint=checkpoint,
                            width=1024,
                            height=1024,
                            steps=28,
                            guidance=5.5,
                            seed=seed,
                            client_action_id=f"{run_id}-james-{index:02d}",
                        )
                        completed = await worker.wait(
                            submitted.job_id,
                            timeout_seconds=generation_timeout,
                            poll_interval_seconds=poll_seconds,
                        )
                        if not completed.outputs:
                            raise RuntimeError(f"attempt {index} returned no output")
                        output = completed.outputs[0]
                        data = await worker.download(output)
                        width, height, digest = _validate_image(data, output.sha256)
                        suffix = Path(output.filename).suffix.lower() or ".png"
                        image_path = output_dir / f"james-{index:02d}-{seed}{suffix}"
                        image_path.write_bytes(data)
                        records.append(
                            {
                                "attempt": index,
                                "prompt": prompt,
                                "negative_prompt": NEGATIVE_PROMPT,
                                "seed": seed,
                                "job_id": completed.job_id,
                                "prompt_id": completed.prompt_id,
                                "workflow_sha256": completed.workflow_sha256,
                                "image_path": str(image_path),
                                "image_sha256": digest,
                                "width": width,
                                "height": height,
                            }
                        )
                    records.append({"worker_health": health})
        except Exception as exc:
            failure = exc
        finally:
            if pod is not None:
                try:
                    async with RunPodControlClient(api_key) as cleanup_client:
                        await cleanup_client.delete_pod(pod.pod_id)
                        try:
                            billing = await cleanup_client.pod_billing(pod.pod_id)
                            billing_records.extend(billing)
                        except Exception as exc:  # evidence, not the primary failure
                            billing_errors.append(f"Pod {pod.pod_id} billing: {exc}")
                except Exception as exc:  # cleanup must be reported alongside original failure
                    cleanup_errors.append(f"Pod {pod.pod_id}: {exc}")

    manifest = {
        "schema_version": 2,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "worker_image": worker_image,
        "image_digest": worker_image.split("@sha256:", 1)[1][:64],
        "pod_id": pod.pod_id if pod else None,
        "gpu": pod.gpu_name if pod else None,
        "hourly_rate_usd": pod.hourly_rate if pod else None,
        "elapsed_seconds": time.monotonic() - started,
        "estimated_compute_cost_usd": (
            pod.hourly_rate * (time.monotonic() - started) / 3600 if pod else None
        ),
        "checkpoint": checkpoint,
        "checkpoint_sha256": checkpoint_sha,
        "pod_transitions": pod_transitions,
        "runtime_config": pod_runtime,
        "health_stage_history": health_stage_history,
        "billing_records": billing_records,
        "billing_errors": billing_errors,
        "cleanup_errors": cleanup_errors,
        "cleanup_succeeded": not cleanup_errors,
        "attempts": records,
        "failure": str(failure) if failure is not None else None,
    }
    manifest_path = output_dir / f"james-batch-{run_id}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if failure is not None:
        detail = str(failure)
        if cleanup_errors:
            detail += "; cleanup incomplete: " + "; ".join(cleanup_errors)
        raise RuntimeError(detail) from failure
    if cleanup_errors:
        raise RuntimeError(
            "generation completed but cleanup was incomplete: " + "; ".join(cleanup_errors)
        )
    return manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempts", type=int, default=6, choices=range(1, 7))
    parser.add_argument("--output-dir", default="runtime-data/runpod-james")
    parser.add_argument("--accept-charges", action="store_true")
    args = parser.parse_args()
    if not args.accept_charges:
        parser.error("--accept-charges is required for the live batch")
    return args


def main() -> int:
    try:
        path = asyncio.run(run(parse_args()))
    except (RunPodError, RunPodWorkerError, RuntimeError, httpx.HTTPError) as exc:
        print(f"James batch failed: {exc}", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
