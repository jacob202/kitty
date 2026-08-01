#!/usr/bin/env python3
"""Run one guarded RunPod Pod -> Kitty worker -> local image smoke test."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import secrets
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateway.runpod_control import (  # noqa: E402
    PodInfo,
    RunPodAmbiguousCreateError,
    RunPodApiError,
    RunPodConfigurationError,
    RunPodControlClient,
)
from gateway.runpod_worker import (  # noqa: E402
    RunPodWorkerAmbiguousSubmissionError,
    RunPodWorkerClient,
    RunPodWorkerError,
)

WORKER_PORT = 8000
WORKFLOW_ID = "text_to_image_v1"
DEFAULT_GPU_TYPE_IDS = (
    "NVIDIA GeForce RTX 3090",
    "NVIDIA RTX A5000",
    "NVIDIA GeForce RTX 4090",
)


class WorkerSmokeError(RuntimeError):
    """The authenticated RunPod worker smoke test failed."""


@dataclass(frozen=True)
class Config:
    api_key: str
    template_id: str | None
    worker_token: str
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
        require_live_secrets: bool,
        require_template: bool,
    ) -> "Config":
        api_key = os.environ.get("RUNPOD_API_KEY", "").strip()
        template_id = os.environ.get("RUNPOD_TEMPLATE_ID", "").strip() or None
        worker_token = os.environ.get(
            "KITTY_WORKER_BEARER_TOKEN", ""
        ).strip()
        if require_live_secrets and not api_key:
            raise RunPodConfigurationError("RUNPOD_API_KEY is required")
        if require_live_secrets and len(worker_token) < 32:
            raise RunPodConfigurationError(
                "KITTY_WORKER_BEARER_TOKEN must contain at least 32 characters"
            )
        if require_template and not template_id:
            raise RunPodConfigurationError(
                "RUNPOD_TEMPLATE_ID is required when creating a Pod"
            )
        gpu_type_ids = tuple(
            item.strip()
            for item in os.environ.get(
                "RUNPOD_GPU_TYPE_IDS", ",".join(DEFAULT_GPU_TYPE_IDS)
            ).split(",")
            if item.strip()
        )
        config = cls(
            api_key=api_key,
            template_id=template_id,
            worker_token=worker_token,
            network_volume_id=(
                os.environ.get("RUNPOD_NETWORK_VOLUME_ID", "").strip() or None
            ),
            checkpoint=os.environ.get(
                "COMFY_CHECKPOINT", "RealCoreXL.safetensors"
            ).strip(),
            gpu_type_ids=gpu_type_ids,
            max_hourly_rate=_env_float("RUNPOD_MAX_HOURLY_RATE", 0.50),
            hard_runtime_minutes=_env_int(
                "RUNPOD_HARD_RUNTIME_MINUTES", 120
            ),
            ready_timeout_seconds=_env_int(
                "RUNPOD_READY_TIMEOUT_SECONDS", 600
            ),
            generation_timeout_seconds=_env_int(
                "RUNPOD_GENERATION_TIMEOUT_SECONDS", 420
            ),
            poll_interval_seconds=_env_float(
                "RUNPOD_POLL_INTERVAL_SECONDS", 4.0
            ),
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
        if not self.gpu_type_ids:
            raise RunPodConfigurationError("RUNPOD_GPU_TYPE_IDS is empty")
        if not self.checkpoint:
            raise RunPodConfigurationError("COMFY_CHECKPOINT is empty")
        if not math.isfinite(self.max_hourly_rate) or self.max_hourly_rate <= 0:
            raise RunPodConfigurationError(
                "RUNPOD_MAX_HOURLY_RATE must be positive and finite"
            )
        if self.hard_runtime_minutes <= 0:
            raise RunPodConfigurationError(
                "RUNPOD_HARD_RUNTIME_MINUTES must be positive"
            )
        if self.ready_timeout_seconds <= 0:
            raise RunPodConfigurationError(
                "RUNPOD_READY_TIMEOUT_SECONDS must be positive"
            )
        if self.generation_timeout_seconds <= 0:
            raise RunPodConfigurationError(
                "RUNPOD_GENERATION_TIMEOUT_SECONDS must be positive"
            )
        if not math.isfinite(self.poll_interval_seconds) or self.poll_interval_seconds <= 0:
            raise RunPodConfigurationError(
                "RUNPOD_POLL_INTERVAL_SECONDS must be positive and finite"
            )
        for name, value in (
            ("COMFY_WIDTH", self.width),
            ("COMFY_HEIGHT", self.height),
        ):
            if not 256 <= value <= 2048 or value % 8:
                raise RunPodConfigurationError(
                    f"{name} must be 256-2048 and divisible by 8"
                )
        if not 1 <= self.steps <= 100:
            raise RunPodConfigurationError(
                "COMFY_STEPS must be between 1 and 100"
            )
        if not math.isfinite(self.guidance) or not 0 <= self.guidance <= 30:
            raise RunPodConfigurationError(
                "COMFY_CFG must be finite and between 0 and 30"
            )


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


def estimated_compute_cost(hourly_rate: float, elapsed_seconds: float) -> float:
    return max(hourly_rate, 0.0) * max(elapsed_seconds, 0.0) / 3600.0


async def reconcile_expired_pods(client: RunPodControlClient) -> list[str]:
    terminated: list[str] = []
    for pod in await client.list_managed_pods():
        if pod.is_expired():
            await client.delete_pod(pod.pod_id)
            terminated.append(pod.pod_id)
    return terminated


async def reconcile_ambiguous_creation(
    client: RunPodControlClient,
    pod_name: str,
) -> list[str]:
    """Delete exact-name managed Pods after a lost create response."""
    try:
        pods = await client.list_pods()
    except RunPodApiError as exc:
        raise WorkerSmokeError(
            "Pod creation was ambiguous and reconciliation also failed; "
            f"inspect RunPod for Pod name {pod_name!r}: {exc}"
        ) from exc
    matches = [pod for pod in pods if pod.name == pod_name and pod.is_managed()]
    deleted: list[str] = []
    failures: list[str] = []
    for pod in matches:
        try:
            await client.delete_pod(pod.pod_id)
            deleted.append(pod.pod_id)
        except RunPodApiError as exc:
            failures.append(f"{pod.pod_id}: {exc}")
    if failures:
        raise WorkerSmokeError(
            "Pod creation was ambiguous and cleanup was incomplete; inspect "
            f"RunPod for Pod name {pod_name!r}: {'; '.join(failures)}"
        )
    return deleted


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
            raise WorkerSmokeError(
                f"Pod {pod_id} entered terminal state {last_status}"
            )
        await asyncio.sleep(poll_interval_seconds)
    raise WorkerSmokeError(
        f"Pod {pod_id} did not reach RUNNING within {timeout_seconds}s; "
        f"last status was {last_status}"
    )


async def wait_for_worker(
    client: RunPodWorkerClient,
    *,
    timeout_seconds: int,
    poll_interval_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "not contacted"
    while time.monotonic() < deadline:
        try:
            await client.assert_ready()
            return
        except (httpx.HTTPError, RunPodWorkerError) as exc:
            last_error = str(exc)
            await asyncio.sleep(poll_interval_seconds)
    raise WorkerSmokeError(
        f"Kitty worker did not become ready within {timeout_seconds}s: "
        f"{last_error}"
    )


def _validate_acknowledgements(
    args: argparse.Namespace,
    *,
    creating_pod: bool,
) -> None:
    if args.dry_run:
        return
    if creating_pod and not args.accept_charges:
        raise WorkerSmokeError(
            "refusing to create a billable Pod without --accept-charges"
        )
    if not creating_pod and not args.accept_continuing_charges:
        raise WorkerSmokeError(
            "an existing Pod continues billing; pass --accept-continuing-charges"
        )
    if args.keep_pod and not args.accept_continuing_charges:
        raise WorkerSmokeError(
            "--keep-pod requires --accept-continuing-charges"
        )


def _write_provenance(
    *,
    output_dir: Path,
    run_id: str,
    started_at: datetime,
    elapsed_seconds: float,
    pod: PodInfo,
    config: Config,
    args: argparse.Namespace,
    worker_job_id: str | None,
    prompt_id: str | None,
    workflow_sha256: str | None,
    seed: int,
    image_path: Path | None,
    image_sha256: str | None,
    actual_cost: float | None,
    pod_terminated: bool,
    termination_error: str | None,
    failure: BaseException | None,
) -> Path:
    payload = {
        "schema_version": 2,
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "pod_id": pod.pod_id,
        "gpu": pod.gpu_name,
        "hourly_rate_usd": pod.hourly_rate,
        "elapsed_seconds": elapsed_seconds,
        "estimated_compute_cost_usd": estimated_compute_cost(
            pod.hourly_rate, elapsed_seconds
        ),
        "actual_cost_usd": actual_cost,
        "cost_reconciliation_status": (
            "reconciled" if actual_cost is not None else "pending"
        ),
        "pod_terminated": pod_terminated,
        "termination_error": termination_error,
        "worker_job_id": worker_job_id,
        "prompt_id": prompt_id,
        "workflow_id": WORKFLOW_ID,
        "workflow_sha256": workflow_sha256,
        "prompt": args.prompt,
        "negative_prompt": config.negative_prompt,
        "checkpoint": config.checkpoint,
        "seed": seed,
        "width": config.width,
        "height": config.height,
        "steps": config.steps,
        "guidance": config.guidance,
        "image_path": str(image_path) if image_path else None,
        "image_sha256": image_sha256,
        "failure_type": type(failure).__name__ if failure else None,
        "failure_message": str(failure) if failure else None,
    }
    path = output_dir / f"runpod-worker-smoke-{run_id}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


async def run_smoke(args: argparse.Namespace) -> Path:
    creating_pod = not bool(args.existing_pod_id)
    config = Config.from_env(
        require_live_secrets=not args.dry_run,
        require_template=creating_pod and not args.dry_run,
    )
    _validate_acknowledgements(args, creating_pod=creating_pod)
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    seed = args.seed if args.seed is not None else secrets.randbits(63)
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        + "-"
        + secrets.token_hex(4)
    )

    if args.dry_run:
        path = output_dir / f"runpod-worker-smoke-plan-{run_id}.json"
        path.write_text(
            json.dumps(
                {
                    "dry_run": True,
                    "run_id": run_id,
                    "creating_pod": creating_pod,
                    "template_id": config.template_id,
                    "worker_port": WORKER_PORT,
                    "workflow_id": WORKFLOW_ID,
                    "checkpoint": config.checkpoint,
                    "gpu_type_ids": config.gpu_type_ids,
                    "max_hourly_rate": config.max_hourly_rate,
                    "seed": seed,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return path

    pod: PodInfo | None = None
    owns_pod = False
    worker_job_id: str | None = None
    prompt_id: str | None = None
    workflow_sha256: str | None = None
    image_path: Path | None = None
    image_sha256: str | None = None
    actual_cost: float | None = None
    termination_error: str | None = None
    failure: BaseException | None = None
    started_at = datetime.now(timezone.utc)
    started_monotonic = time.monotonic()

    async with RunPodControlClient(config.api_key) as runpod:
        expired = await reconcile_expired_pods(runpod)
        if expired:
            print(f"Terminated {len(expired)} expired Kitty Pod(s).")

        if args.existing_pod_id:
            pod = await runpod.get_pod(args.existing_pod_id)
            if not pod.is_managed():
                raise WorkerSmokeError(
                    f"refusing unmanaged existing Pod {pod.pod_id}"
                )
        else:
            if config.template_id is None:
                raise RunPodConfigurationError(
                    "RUNPOD_TEMPLATE_ID is required"
                )
            try:
                pod = await runpod.create_image_pod(
                    template_id=config.template_id,
                    gpu_type_ids=config.gpu_type_ids,
                    max_hourly_rate=config.max_hourly_rate,
                    hard_runtime_minutes=config.hard_runtime_minutes,
                    ports=(f"{WORKER_PORT}/http",),
                    network_volume_id=config.network_volume_id,
                    cloud_type=args.cloud_type,
                    container_disk_gb=args.container_disk_gb,
                    volume_gb=args.volume_gb,
                    env={
                        "KITTY_WORKER_BEARER_TOKEN": config.worker_token,
                        "COMFY_CHECKPOINT": config.checkpoint,
                        "KITTY_ALLOWED_CHECKPOINTS": config.checkpoint,
                    },
                    name_suffix=run_id,
                )
            except RunPodAmbiguousCreateError as exc:
                deleted = await reconcile_ambiguous_creation(
                    runpod, exc.pod_name
                )
                detail = (
                    f"; deleted {len(deleted)} matching Pod(s)"
                    if deleted
                    else "; no matching managed Pod was visible"
                )
                raise WorkerSmokeError(
                    "Pod creation lost confirmation and was not retried" + detail
                ) from exc
            owns_pod = True

        if pod.hourly_rate <= 0:
            raise WorkerSmokeError(
                f"Pod {pod.pod_id} has no positive finite hourly rate"
            )
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
            async with RunPodWorkerClient(
                pod.proxy_url(WORKER_PORT),
                config.worker_token,
            ) as worker:
                await wait_for_worker(
                    worker,
                    timeout_seconds=config.ready_timeout_seconds,
                    poll_interval_seconds=config.poll_interval_seconds,
                )
                submitted = await worker.submit(
                    workflow_id=WORKFLOW_ID,
                    prompt=args.prompt,
                    negative_prompt=config.negative_prompt,
                    checkpoint=config.checkpoint,
                    width=config.width,
                    height=config.height,
                    steps=config.steps,
                    guidance=config.guidance,
                    seed=seed,
                    client_action_id=f"smoke-{run_id}",
                )
                worker_job_id = submitted.job_id
                completed = await worker.wait(
                    submitted.job_id,
                    timeout_seconds=config.generation_timeout_seconds,
                    poll_interval_seconds=config.poll_interval_seconds,
                )
                prompt_id = completed.prompt_id
                workflow_sha256 = completed.workflow_sha256
                if not completed.outputs:
                    raise WorkerSmokeError(
                        "worker completed without an output"
                    )
                output = completed.outputs[0]
                image_bytes = await worker.download(output)
                image_sha256 = hashlib.sha256(image_bytes).hexdigest()
                if output.sha256 and image_sha256 != output.sha256:
                    raise WorkerSmokeError(
                        "downloaded image checksum did not match worker metadata"
                    )
                suffix = Path(output.filename).suffix.lower() or ".png"
                image_path = (
                    output_dir / f"kitty-runpod-worker-{run_id}{suffix}"
                )
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
                actual_cost = None

    elapsed = time.monotonic() - started_monotonic
    _write_provenance(
        output_dir=output_dir,
        run_id=run_id,
        started_at=started_at,
        elapsed_seconds=elapsed,
        pod=pod,
        config=config,
        args=args,
        worker_job_id=worker_job_id,
        prompt_id=prompt_id,
        workflow_sha256=workflow_sha256,
        seed=seed,
        image_path=image_path,
        image_sha256=image_sha256,
        actual_cost=actual_cost,
        pod_terminated=owns_pod and not args.keep_pod and not termination_error,
        termination_error=termination_error,
        failure=failure,
    )
    if termination_error:
        raise WorkerSmokeError(
            f"automatic Pod termination failed: {termination_error}; "
            f"terminate Pod {pod.pod_id} manually"
        ) from failure
    if failure is not None:
        raise failure
    if image_path is None:
        raise WorkerSmokeError("generation finished without a local image")
    return image_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one authenticated RunPod worker image smoke test."
    )
    parser.add_argument("--prompt", required=True)
    parser.add_argument(
        "--output-dir", default="data/runpod-worker-smoke"
    )
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
    parser.add_argument(
        "--accept-continuing-charges", action="store_true"
    )
    return parser


async def async_main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = await run_smoke(args)
    except (
        RunPodConfigurationError,
        RunPodWorkerAmbiguousSubmissionError,
        RunPodWorkerError,
        WorkerSmokeError,
        httpx.HTTPError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(result)
    return 0


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
