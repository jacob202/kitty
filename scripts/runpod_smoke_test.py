#!/usr/bin/env python3
"""Run one guarded RunPod -> ComfyUI -> local image smoke test.

This is deliberately a development proof, not Kitty's final RunPod worker. It
uses the RunPod HTTP proxy to reach raw ComfyUI on port 8188, which is publicly
reachable while the Pod is running. The command therefore requires an explicit
``--allow-public-comfyui`` acknowledgement and must not be used for sensitive
images or prompts.

A real Pod is never created unless ``--accept-charges`` is present. A Pod
created by this command is terminated in ``finally`` unless the caller supplies
both ``--keep-pod`` and ``--accept-continuing-charges``.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import secrets
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateway.runpod_control import (  # noqa: E402
    PodInfo,
    RunPodApiError,
    RunPodConfigurationError,
    RunPodControlClient,
)

COMFY_PORT = 8188
REQUIRED_COMFY_NODES = frozenset(
    {
        "CheckpointLoaderSimple",
        "CLIPTextEncode",
        "EmptyLatentImage",
        "KSampler",
        "VAEDecode",
        "SaveImage",
    }
)
DEFAULT_GPU_TYPE_IDS = (
    "NVIDIA GeForce RTX 3090",
    "NVIDIA RTX A5000",
    "NVIDIA GeForce RTX 4090",
)


class SmokeTestError(RuntimeError):
    """The smoke test could not complete safely."""


class AmbiguousSubmissionError(SmokeTestError):
    """ComfyUI may have accepted a prompt, so the request must not be retried."""


@dataclass(frozen=True)
class SmokeConfig:
    api_key: str
    template_id: str | None
    network_volume_id: str | None
    checkpoint: str
    gpu_type_ids: tuple[str, ...]
    max_hourly_rate: float
    hard_runtime_minutes: int
    ready_timeout_seconds: int
    generation_timeout_seconds: int
    poll_interval_seconds: float
    width: int
    height: int
    steps: int
    guidance: float
    negative_prompt: str

    @classmethod
    def from_env(
        cls,
        *,
        require_template: bool,
        require_api_key: bool = True,
    ) -> "SmokeConfig":
        api_key = os.environ.get("RUNPOD_API_KEY", "").strip()
        template_id = os.environ.get("RUNPOD_TEMPLATE_ID", "").strip() or None
        if require_api_key and not api_key:
            raise RunPodConfigurationError("RUNPOD_API_KEY is required")
        if require_template and not template_id:
            raise RunPodConfigurationError(
                "RUNPOD_TEMPLATE_ID is required when creating a Pod"
            )

        gpu_type_ids = tuple(
            value.strip()
            for value in os.environ.get(
                "RUNPOD_GPU_TYPE_IDS", ",".join(DEFAULT_GPU_TYPE_IDS)
            ).split(",")
            if value.strip()
        )
        if not gpu_type_ids:
            raise RunPodConfigurationError("RUNPOD_GPU_TYPE_IDS is empty")

        config = cls(
            api_key=api_key,
            template_id=template_id,
            network_volume_id=(
                os.environ.get("RUNPOD_NETWORK_VOLUME_ID", "").strip() or None
            ),
            checkpoint=os.environ.get(
                "COMFY_CHECKPOINT", "RealCoreXL.safetensors"
            ).strip(),
            gpu_type_ids=gpu_type_ids,
            max_hourly_rate=_env_float("RUNPOD_MAX_HOURLY_RATE", 0.50),
            hard_runtime_minutes=_env_int("RUNPOD_HARD_RUNTIME_MINUTES", 120),
            ready_timeout_seconds=_env_int("RUNPOD_READY_TIMEOUT_SECONDS", 600),
            generation_timeout_seconds=_env_int(
                "RUNPOD_GENERATION_TIMEOUT_SECONDS", 420
            ),
            poll_interval_seconds=_env_float("RUNPOD_POLL_INTERVAL_SECONDS", 4.0),
            width=_env_int("COMFY_WIDTH", 1024),
            height=_env_int("COMFY_HEIGHT", 1024),
            steps=_env_int("COMFY_STEPS", 20),
            guidance=_env_float("COMFY_CFG", 5.0),
            negative_prompt=os.environ.get(
                "COMFY_NEGATIVE_PROMPT",
                "worst quality, low quality, bad anatomy, deformed, watermark, text",
            ),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if not self.checkpoint:
            raise RunPodConfigurationError("COMFY_CHECKPOINT must not be empty")
        if self.max_hourly_rate <= 0:
            raise RunPodConfigurationError(
                "RUNPOD_MAX_HOURLY_RATE must be greater than zero"
            )
        if self.hard_runtime_minutes <= 0:
            raise RunPodConfigurationError(
                "RUNPOD_HARD_RUNTIME_MINUTES must be positive"
            )
        if self.ready_timeout_seconds <= 0 or self.generation_timeout_seconds <= 0:
            raise RunPodConfigurationError("timeouts must be positive")
        if self.poll_interval_seconds <= 0:
            raise RunPodConfigurationError(
                "RUNPOD_POLL_INTERVAL_SECONDS must be positive"
            )
        if not 256 <= self.width <= 2048 or self.width % 8:
            raise RunPodConfigurationError(
                "COMFY_WIDTH must be 256-2048 and divisible by 8"
            )
        if not 256 <= self.height <= 2048 or self.height % 8:
            raise RunPodConfigurationError(
                "COMFY_HEIGHT must be 256-2048 and divisible by 8"
            )
        if not 1 <= self.steps <= 100:
            raise RunPodConfigurationError("COMFY_STEPS must be between 1 and 100")
        if not 0 <= self.guidance <= 30:
            raise RunPodConfigurationError("COMFY_CFG must be between 0 and 30")


@dataclass(frozen=True)
class ComfyOutput:
    filename: str
    subfolder: str
    output_type: str


class ComfyUIClient:
    """Small client for the official ComfyUI HTTP API."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    async def __aenter__(self) -> "ComfyUIClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def assert_ready(self, checkpoint: str) -> None:
        response = await self._client.get(f"{self._base_url}/object_info")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise SmokeTestError("ComfyUI /object_info response was not an object")

        missing = sorted(REQUIRED_COMFY_NODES.difference(payload))
        if missing:
            raise SmokeTestError(
                "ComfyUI is missing required nodes: " + ", ".join(missing)
            )

        checkpoint_loader = payload.get("CheckpointLoaderSimple")
        available = _checkpoint_options(checkpoint_loader)
        if available and checkpoint not in available:
            preview = ", ".join(sorted(available)[:10])
            raise SmokeTestError(
                f"checkpoint {checkpoint!r} is not installed; available: {preview}"
            )

    async def submit(self, workflow: Mapping[str, object]) -> str:
        try:
            response = await self._client.post(
                f"{self._base_url}/prompt",
                json={"prompt": dict(workflow)},
            )
        except httpx.RequestError as exc:
            raise AmbiguousSubmissionError(
                "connection failed while submitting to ComfyUI; the prompt may have "
                "been accepted, so Kitty will not retry automatically"
            ) from exc

        if response.status_code >= 400:
            raise SmokeTestError(
                f"ComfyUI rejected the workflow ({response.status_code}): "
                f"{response.text[:500]}"
            )
        payload = response.json()
        prompt_id = payload.get("prompt_id") if isinstance(payload, Mapping) else None
        if not prompt_id:
            raise SmokeTestError("ComfyUI response did not include prompt_id")
        return str(prompt_id)

    async def wait_for_output(
        self,
        prompt_id: str,
        *,
        timeout_seconds: int,
        poll_interval_seconds: float,
    ) -> ComfyOutput:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            response = await self._client.get(
                f"{self._base_url}/history/{prompt_id}"
            )
            response.raise_for_status()
            payload = response.json()
            output = parse_history_output(payload, prompt_id)
            if output is not None:
                return output
            await asyncio.sleep(poll_interval_seconds)
        raise SmokeTestError(
            f"ComfyUI prompt {prompt_id} did not finish within {timeout_seconds}s"
        )

    async def download(self, output: ComfyOutput) -> bytes:
        response = await self._client.get(
            f"{self._base_url}/view",
            params={
                "filename": output.filename,
                "subfolder": output.subfolder,
                "type": output.output_type,
            },
        )
        response.raise_for_status()
        if not response.content:
            raise SmokeTestError("ComfyUI returned an empty image")
        return response.content


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RunPodConfigurationError(f"{name} must be an integer") from exc


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise RunPodConfigurationError(f"{name} must be a number") from exc


def _checkpoint_options(value: object) -> set[str]:
    if not isinstance(value, Mapping):
        return set()
    inputs = value.get("input")
    if not isinstance(inputs, Mapping):
        return set()
    required = inputs.get("required")
    if not isinstance(required, Mapping):
        return set()
    checkpoint = required.get("ckpt_name")
    if not isinstance(checkpoint, Sequence) or isinstance(checkpoint, (str, bytes)):
        return set()
    if not checkpoint:
        return set()
    choices = checkpoint[0]
    if not isinstance(choices, Sequence) or isinstance(choices, (str, bytes)):
        return set()
    return {str(item) for item in choices}


def build_workflow(
    *,
    prompt: str,
    negative_prompt: str,
    checkpoint: str,
    width: int,
    height: int,
    steps: int,
    guidance: float,
    seed: int,
) -> dict[str, dict[str, object]]:
    """Build the one allowlisted SDXL smoke-test workflow."""

    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["1", 1]},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative_prompt, "clip": ["1", 1]},
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": guidance,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
        },
        "6": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
        },
        "7": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "KittySmoke", "images": ["6", 0]},
        },
    }


def parse_history_output(payload: object, prompt_id: str) -> ComfyOutput | None:
    if not isinstance(payload, Mapping):
        raise SmokeTestError("ComfyUI history response was not an object")
    entry = payload.get(prompt_id)
    if entry is None:
        return None
    if not isinstance(entry, Mapping):
        raise SmokeTestError("ComfyUI history entry was not an object")

    status = entry.get("status")
    if isinstance(status, Mapping) and status.get("status_str") in {
        "error",
        "failed",
    }:
        raise SmokeTestError(
            f"ComfyUI generation failed: {status.get('messages') or status}"
        )

    outputs = entry.get("outputs")
    if not isinstance(outputs, Mapping):
        return None
    for node_output in outputs.values():
        if not isinstance(node_output, Mapping):
            continue
        images = node_output.get("images")
        if not isinstance(images, Sequence) or isinstance(images, (str, bytes)):
            continue
        for image in images:
            if not isinstance(image, Mapping) or not image.get("filename"):
                continue
            return ComfyOutput(
                filename=str(image["filename"]),
                subfolder=str(image.get("subfolder") or ""),
                output_type=str(image.get("type") or "output"),
            )
    return None


def estimated_compute_cost(hourly_rate: float, elapsed_seconds: float) -> float:
    return max(hourly_rate, 0.0) * max(elapsed_seconds, 0.0) / 3600.0


async def reconcile_expired_pods(client: RunPodControlClient) -> list[str]:
    """Terminate only Kitty-managed Pods whose embedded hard expiry has passed."""

    terminated: list[str] = []
    for pod in await client.list_managed_pods():
        if pod.is_expired():
            await client.delete_pod(pod.pod_id)
            terminated.append(pod.pod_id)
    return terminated


async def wait_for_running_pod(
    client: RunPodControlClient,
    pod_id: str,
    *,
    timeout_seconds: int,
    poll_interval_seconds: float,
) -> PodInfo:
    deadline = time.monotonic() + timeout_seconds
    last_status = "UNKNOWN"
    while time.monotonic() < deadline:
        pod = await client.get_pod(pod_id)
        last_status = pod.desired_status
        if last_status == "RUNNING":
            return pod
        if last_status in {"EXITED", "TERMINATED"}:
            raise SmokeTestError(
                f"RunPod Pod {pod_id} entered terminal state {last_status}"
            )
        await asyncio.sleep(poll_interval_seconds)
    raise SmokeTestError(
        f"RunPod Pod {pod_id} did not reach RUNNING within {timeout_seconds}s; "
        f"last status was {last_status}"
    )


async def wait_for_comfyui(
    client: ComfyUIClient,
    checkpoint: str,
    *,
    timeout_seconds: int,
    poll_interval_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "not contacted"
    while time.monotonic() < deadline:
        try:
            await client.assert_ready(checkpoint)
            return
        except (httpx.HTTPError, SmokeTestError) as exc:
            last_error = str(exc)
            await asyncio.sleep(poll_interval_seconds)
    raise SmokeTestError(
        f"ComfyUI did not become ready within {timeout_seconds}s: {last_error}"
    )


def _write_provenance(
    *,
    output_dir: Path,
    started_at: datetime,
    elapsed: float,
    pod: PodInfo,
    config: SmokeConfig,
    args: argparse.Namespace,
    seed: int,
    workflow_hash: str,
    prompt_id: str | None,
    image_path: Path | None,
    actual_cost: float | None,
    pod_terminated: bool,
    termination_error: str | None,
    failure: BaseException | None,
) -> Path:
    provenance = {
        "schema_version": 1,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "pod_id": pod.pod_id,
        "gpu": pod.gpu_name,
        "hourly_rate_usd": pod.hourly_rate,
        "elapsed_seconds": elapsed,
        "estimated_compute_cost_usd": estimated_compute_cost(
            pod.hourly_rate, elapsed
        ),
        "actual_cost_usd": actual_cost,
        "cost_reconciliation_status": (
            "reconciled" if actual_cost is not None else "pending"
        ),
        "pod_terminated": pod_terminated,
        "termination_error": termination_error,
        "failure_type": type(failure).__name__ if failure else None,
        "failure_message": str(failure) if failure else None,
        "prompt_id": prompt_id,
        "prompt": args.prompt,
        "negative_prompt": config.negative_prompt,
        "checkpoint": config.checkpoint,
        "seed": seed,
        "width": config.width,
        "height": config.height,
        "steps": config.steps,
        "guidance": config.guidance,
        "workflow_sha256": workflow_hash,
        "image_path": str(image_path) if image_path else None,
    }
    path = output_dir / "runpod-smoke-provenance.json"
    path.write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    return path


async def run_smoke(args: argparse.Namespace) -> Path:
    creating_pod = not bool(args.existing_pod_id)
    config = SmokeConfig.from_env(
        require_template=creating_pod and not args.dry_run,
        require_api_key=not args.dry_run,
    )
    _validate_charge_acknowledgements(args, creating_pod=creating_pod)

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    seed = args.seed if args.seed is not None else secrets.randbits(63)
    workflow = build_workflow(
        prompt=args.prompt,
        negative_prompt=config.negative_prompt,
        checkpoint=config.checkpoint,
        width=config.width,
        height=config.height,
        steps=config.steps,
        guidance=config.guidance,
        seed=seed,
    )
    workflow_hash = hashlib.sha256(
        json.dumps(workflow, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    if args.dry_run:
        plan_path = output_dir / "runpod-smoke-plan.json"
        plan_path.write_text(
            json.dumps(
                {
                    "dry_run": True,
                    "creating_pod": creating_pod,
                    "template_id": config.template_id,
                    "gpu_type_ids": config.gpu_type_ids,
                    "max_hourly_rate": config.max_hourly_rate,
                    "checkpoint": config.checkpoint,
                    "workflow_sha256": workflow_hash,
                    "seed": seed,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return plan_path

    pod: PodInfo | None = None
    owns_pod = False
    started_monotonic = time.monotonic()
    started_at = datetime.now(timezone.utc)
    prompt_id: str | None = None
    image_path: Path | None = None
    actual_cost: float | None = None
    termination_error: str | None = None
    failure: BaseException | None = None

    async with RunPodControlClient(config.api_key) as runpod:
        expired = await reconcile_expired_pods(runpod)
        if expired:
            print(f"Terminated {len(expired)} expired Kitty Pod(s).")

        if args.existing_pod_id:
            pod = await runpod.get_pod(args.existing_pod_id)
        else:
            if config.template_id is None:
                raise RunPodConfigurationError("RUNPOD_TEMPLATE_ID is required")
            pod = await runpod.create_image_pod(
                template_id=config.template_id,
                gpu_type_ids=config.gpu_type_ids,
                max_hourly_rate=config.max_hourly_rate,
                hard_runtime_minutes=config.hard_runtime_minutes,
                ports=(f"{COMFY_PORT}/http",),
                network_volume_id=config.network_volume_id,
                cloud_type=args.cloud_type,
                container_disk_gb=args.container_disk_gb,
                volume_gb=args.volume_gb,
            )
            owns_pod = True

        print(
            f"RunPod Pod {pod.pod_id} selected; GPU={pod.gpu_name}; "
            f"rate=${pod.hourly_rate:.4f}/hr"
        )

        try:
            pod = await wait_for_running_pod(
                runpod,
                pod.pod_id,
                timeout_seconds=config.ready_timeout_seconds,
                poll_interval_seconds=config.poll_interval_seconds,
            )
            comfy_url = pod.proxy_url(COMFY_PORT)
            async with ComfyUIClient(comfy_url) as comfy:
                await wait_for_comfyui(
                    comfy,
                    config.checkpoint,
                    timeout_seconds=config.ready_timeout_seconds,
                    poll_interval_seconds=config.poll_interval_seconds,
                )
                prompt_id = await comfy.submit(workflow)
                output = await comfy.wait_for_output(
                    prompt_id,
                    timeout_seconds=config.generation_timeout_seconds,
                    poll_interval_seconds=config.poll_interval_seconds,
                )
                image_bytes = await comfy.download(output)

            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            image_path = output_dir / f"kitty-runpod-smoke-{timestamp}.png"
            image_path.write_bytes(image_bytes)
        except BaseException as exc:
            failure = exc
        finally:
            if owns_pod and not args.keep_pod:
                try:
                    await runpod.delete_pod(pod.pod_id)
                except RunPodApiError as exc:
                    termination_error = str(exc)
            try:
                actual_cost = await runpod.actual_cost(pod.pod_id)
            except RunPodApiError:
                # Billing frequently lags Pod termination. Preserve unknown honestly.
                actual_cost = None

    elapsed = time.monotonic() - started_monotonic
    _write_provenance(
        output_dir=output_dir,
        started_at=started_at,
        elapsed=elapsed,
        pod=pod,
        config=config,
        args=args,
        seed=seed,
        workflow_hash=workflow_hash,
        prompt_id=prompt_id,
        image_path=image_path,
        actual_cost=actual_cost,
        pod_terminated=owns_pod and not args.keep_pod and not termination_error,
        termination_error=termination_error,
        failure=failure,
    )

    if termination_error:
        message = (
            "automatic Pod termination failed: "
            f"{termination_error}. Terminate Pod {pod.pod_id} in the RunPod console now."
        )
        raise SmokeTestError(message) from failure
    if failure is not None:
        raise failure
    if image_path is None:
        raise SmokeTestError("generation finished without a local image path")
    return image_path


def _validate_charge_acknowledgements(
    args: argparse.Namespace,
    *,
    creating_pod: bool,
) -> None:
    if args.dry_run:
        return
    if not args.allow_public_comfyui:
        raise SmokeTestError(
            "raw ComfyUI will be publicly reachable through the RunPod proxy; "
            "pass --allow-public-comfyui for this non-sensitive development smoke test"
        )
    if creating_pod and not args.accept_charges:
        raise SmokeTestError(
            "refusing to create a billable Pod without --accept-charges"
        )
    if not creating_pod and not args.accept_continuing_charges:
        raise SmokeTestError(
            "an existing Pod continues billing; pass --accept-continuing-charges"
        )
    if args.keep_pod and not args.accept_continuing_charges:
        raise SmokeTestError(
            "--keep-pod requires --accept-continuing-charges"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one guarded RunPod/ComfyUI image-generation smoke test."
    )
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output-dir", default="outputs/runpod-smoke")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--existing-pod-id")
    parser.add_argument(
        "--cloud-type",
        choices=("COMMUNITY", "SECURE"),
        default="COMMUNITY",
    )
    parser.add_argument("--container-disk-gb", type=int, default=30)
    parser.add_argument("--volume-gb", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--accept-charges", action="store_true")
    parser.add_argument("--keep-pod", action="store_true")
    parser.add_argument("--accept-continuing-charges", action="store_true")
    parser.add_argument("--allow-public-comfyui", action="store_true")
    return parser


async def async_main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = await run_smoke(args)
    except (RunPodConfigurationError, SmokeTestError, httpx.HTTPError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(result)
    return 0


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
