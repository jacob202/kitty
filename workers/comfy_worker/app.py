"""Authenticated, allowlisted Kitty worker that fronts a private ComfyUI server."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import time
import uuid
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

DEFAULT_COMFY_URL = "http://127.0.0.1:8188"
DEFAULT_WORKFLOW_ROOT = Path("/opt/kitty/workflows")
DEFAULT_JOB_ROOT = Path("/workspace/jobs")
MAX_REQUEST_BYTES = 128 * 1024


class WorkerConfigurationError(RuntimeError):
    """Worker runtime configuration or workflow bundle is invalid."""


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


TERMINAL_STATUSES = frozenset(
    {JobStatus.CANCELLED, JobStatus.SUCCEEDED, JobStatus.FAILED}
)


class JobRequest(BaseModel):
    workflow_id: str = Field(pattern=r"^[a-z0-9_-]{1,80}$")
    prompt: str = Field(min_length=1, max_length=20_000)
    negative_prompt: str = Field(default="", max_length=20_000)
    checkpoint: str | None = Field(default=None, max_length=255)
    width: int = Field(default=1024, ge=256, le=2048)
    height: int = Field(default=1024, ge=256, le=2048)
    steps: int = Field(default=20, ge=1, le=100)
    guidance: float = Field(default=5.0, ge=0, le=30)
    seed: int | None = Field(default=None, ge=0, le=2**63 - 1)
    count: int = Field(default=1, ge=1, le=1)
    client_action_id: str | None = Field(default=None, max_length=200)

    @field_validator("width", "height")
    @classmethod
    def dimensions_are_divisible_by_eight(cls, value: int) -> int:
        if value % 8:
            raise ValueError("dimensions must be divisible by 8")
        return value

    @field_validator("checkpoint")
    @classmethod
    def checkpoint_is_a_basename(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        if not clean:
            return None
        if Path(clean).name != clean or "/" in clean or "\\" in clean:
            raise ValueError("checkpoint must be a filename, not a path")
        return clean


@dataclass(frozen=True)
class WorkerConfig:
    bearer_token: str
    comfy_url: str = DEFAULT_COMFY_URL
    workflow_root: Path = DEFAULT_WORKFLOW_ROOT
    job_root: Path = DEFAULT_JOB_ROOT
    default_checkpoint: str = "RealCoreXL.safetensors"
    allowed_checkpoints: frozenset[str] = frozenset({"RealCoreXL.safetensors"})
    generation_timeout_seconds: int = 420
    poll_interval_seconds: float = 2.0
    max_request_bytes: int = MAX_REQUEST_BYTES

    @classmethod
    def from_env(cls) -> "WorkerConfig":
        token = os.environ.get("KITTY_WORKER_BEARER_TOKEN", "").strip()
        default_checkpoint = os.environ.get(
            "COMFY_CHECKPOINT", "RealCoreXL.safetensors"
        ).strip()
        raw_allowed = os.environ.get(
            "KITTY_ALLOWED_CHECKPOINTS", default_checkpoint
        )
        allowed = frozenset(
            item.strip() for item in raw_allowed.split(",") if item.strip()
        )
        config = cls(
            bearer_token=token,
            comfy_url=os.environ.get("COMFY_URL", DEFAULT_COMFY_URL).rstrip("/"),
            workflow_root=Path(
                os.environ.get("KITTY_WORKFLOW_ROOT", str(DEFAULT_WORKFLOW_ROOT))
            ),
            job_root=Path(os.environ.get("KITTY_JOB_ROOT", str(DEFAULT_JOB_ROOT))),
            default_checkpoint=default_checkpoint,
            allowed_checkpoints=allowed,
            generation_timeout_seconds=_env_int(
                "KITTY_GENERATION_TIMEOUT_SECONDS", 420
            ),
            poll_interval_seconds=_env_float("KITTY_POLL_INTERVAL_SECONDS", 2.0),
            max_request_bytes=_env_int(
                "KITTY_MAX_REQUEST_BYTES", MAX_REQUEST_BYTES
            ),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if len(self.bearer_token) < 32:
            raise WorkerConfigurationError(
                "KITTY_WORKER_BEARER_TOKEN must contain at least 32 characters"
            )
        if not self.comfy_url.startswith(("http://", "https://")):
            raise WorkerConfigurationError("COMFY_URL must use HTTP or HTTPS")
        if not self.default_checkpoint:
            raise WorkerConfigurationError("COMFY_CHECKPOINT must not be empty")
        if self.default_checkpoint not in self.allowed_checkpoints:
            raise WorkerConfigurationError(
                "COMFY_CHECKPOINT must be included in KITTY_ALLOWED_CHECKPOINTS"
            )
        if self.generation_timeout_seconds <= 0:
            raise WorkerConfigurationError(
                "KITTY_GENERATION_TIMEOUT_SECONDS must be positive"
            )
        if self.poll_interval_seconds <= 0:
            raise WorkerConfigurationError(
                "KITTY_POLL_INTERVAL_SECONDS must be positive"
            )
        if self.max_request_bytes <= 0:
            raise WorkerConfigurationError(
                "KITTY_MAX_REQUEST_BYTES must be positive"
            )


@dataclass
class OutputAsset:
    asset_id: str
    filename: str
    media_type: str
    size_bytes: int
    sha256: str
    path: str


@dataclass
class JobRecord:
    job_id: str
    status: JobStatus
    request: dict[str, Any]
    workflow_sha256: str
    created_at: str
    updated_at: str
    prompt_id: str | None = None
    error: str | None = None
    submission_state: str = "not_submitted"
    outputs: list[OutputAsset] = field(default_factory=list)

    def public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["outputs"] = [
            {
                "asset_id": item.asset_id,
                "filename": item.filename,
                "media_type": item.media_type,
                "size_bytes": item.size_bytes,
                "sha256": item.sha256,
                "download_url": (
                    f"/v1/jobs/{self.job_id}/outputs/{item.asset_id}"
                ),
            }
            for item in self.outputs
        ]
        return payload


@dataclass(frozen=True)
class WorkflowBundle:
    workflow_id: str
    workflow_version: int
    workflow_sha256: str
    workflow: dict[str, Any]
    bindings: dict[str, dict[str, str]]
    output_nodes: frozenset[str]
    required_node_types: frozenset[str]

    @classmethod
    def load(cls, root: Path, workflow_id: str) -> "WorkflowBundle":
        if Path(workflow_id).name != workflow_id:
            raise WorkerConfigurationError("invalid workflow id")
        bundle_dir = root / workflow_id
        workflow_path = bundle_dir / "workflow-api.json"
        manifest_path = bundle_dir / "manifest.yaml"
        try:
            workflow_bytes = workflow_path.read_bytes()
            workflow = json.loads(workflow_bytes)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise WorkerConfigurationError(
                f"workflow {workflow_id!r} is not installed"
            ) from exc
        except json.JSONDecodeError as exc:
            raise WorkerConfigurationError(
                f"workflow {workflow_id!r} bundle contains invalid JSON"
            ) from exc

        actual_hash = hashlib.sha256(workflow_bytes).hexdigest()
        expected_hash = str(manifest.get("workflow_sha256") or "")
        if actual_hash != expected_hash:
            raise WorkerConfigurationError(
                f"workflow {workflow_id!r} hash mismatch"
            )
        if str(manifest.get("workflow_id") or "") != workflow_id:
            raise WorkerConfigurationError("workflow manifest id mismatch")
        if not isinstance(workflow, dict):
            raise WorkerConfigurationError("workflow must be a JSON object")

        raw_bindings = manifest.get("bindings")
        if not isinstance(raw_bindings, dict):
            raise WorkerConfigurationError("workflow manifest bindings are invalid")
        bindings: dict[str, dict[str, str]] = {}
        required_types: set[str] = set()
        for name, raw_binding in raw_bindings.items():
            if not isinstance(raw_binding, dict):
                raise WorkerConfigurationError(f"binding {name!r} is invalid")
            binding = {
                "node_id": str(raw_binding.get("node_id") or ""),
                "input": str(raw_binding.get("input") or ""),
                "expected_class_type": str(
                    raw_binding.get("expected_class_type") or ""
                ),
            }
            if not all(binding.values()):
                raise WorkerConfigurationError(f"binding {name!r} is incomplete")
            node = workflow.get(binding["node_id"])
            if not isinstance(node, dict):
                raise WorkerConfigurationError(
                    f"binding {name!r} references a missing node"
                )
            if node.get("class_type") != binding["expected_class_type"]:
                raise WorkerConfigurationError(
                    f"binding {name!r} node type changed unexpectedly"
                )
            inputs = node.get("inputs")
            if not isinstance(inputs, dict) or binding["input"] not in inputs:
                raise WorkerConfigurationError(
                    f"binding {name!r} references a missing input"
                )
            required_types.add(binding["expected_class_type"])
            bindings[str(name)] = binding

        raw_output_nodes = manifest.get("output_nodes")
        if not isinstance(raw_output_nodes, list) or not raw_output_nodes:
            raise WorkerConfigurationError("workflow output_nodes are invalid")
        output_nodes = frozenset(str(item) for item in raw_output_nodes)
        for node_id in output_nodes:
            node = workflow.get(node_id)
            if not isinstance(node, dict):
                raise WorkerConfigurationError("workflow output node is missing")
            required_types.add(str(node.get("class_type") or ""))

        return cls(
            workflow_id=workflow_id,
            workflow_version=int(manifest.get("workflow_version") or 1),
            workflow_sha256=actual_hash,
            workflow=cast(dict[str, Any], workflow),
            bindings=bindings,
            output_nodes=output_nodes,
            required_node_types=frozenset(required_types),
        )

    def compile(self, request: JobRequest, checkpoint: str) -> dict[str, Any]:
        values: dict[str, object] = {
            "prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "checkpoint": checkpoint,
            "width": request.width,
            "height": request.height,
            "steps": request.steps,
            "guidance": request.guidance,
            "seed": request.seed if request.seed is not None else uuid.uuid4().int >> 65,
            "batch_size": request.count,
        }
        compiled = deepcopy(self.workflow)
        for name, value in values.items():
            binding = self.bindings.get(name)
            if binding is None:
                continue
            node = compiled[binding["node_id"]]
            node["inputs"][binding["input"]] = value
        return compiled


class WorkerRuntime:
    def __init__(
        self,
        config: WorkerConfig,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self.jobs: dict[str, JobRecord] = {}
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.execution_lock = asyncio.Lock()
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(timeout=30.0)
        self.config.job_root.mkdir(parents=True, exist_ok=True)
        self._load_existing_jobs()

    async def close(self) -> None:
        for task in self.tasks.values():
            if not task.done():
                task.cancel()
        if self._owns_client:
            await self.client.aclose()

    def _load_existing_jobs(self) -> None:
        for state_path in self.config.job_root.glob("*/job.json"):
            try:
                raw = json.loads(state_path.read_text(encoding="utf-8"))
                status_value = JobStatus(str(raw["status"]))
                if status_value not in TERMINAL_STATUSES:
                    status_value = JobStatus.FAILED
                    raw["error"] = "worker restarted before job completion"
                outputs = [
                    OutputAsset(**item)
                    for item in raw.get("outputs", [])
                    if isinstance(item, dict)
                ]
                record = JobRecord(
                    job_id=str(raw["job_id"]),
                    status=status_value,
                    request=dict(raw.get("request") or {}),
                    workflow_sha256=str(raw.get("workflow_sha256") or ""),
                    created_at=str(raw.get("created_at") or _utc_now()),
                    updated_at=_utc_now(),
                    prompt_id=(
                        str(raw["prompt_id"]) if raw.get("prompt_id") else None
                    ),
                    error=str(raw["error"]) if raw.get("error") else None,
                    submission_state=str(
                        raw.get("submission_state") or "not_submitted"
                    ),
                    outputs=outputs,
                )
                self.jobs[record.job_id] = record
                self._persist(record)
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue

    def _persist(self, record: JobRecord) -> None:
        job_dir = self.config.job_root / record.job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        payload = asdict(record)
        payload["status"] = record.status.value
        tmp_path = job_dir / "job.json.tmp"
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp_path.replace(job_dir / "job.json")

    def update(
        self,
        record: JobRecord,
        *,
        job_status: JobStatus | None = None,
        error: str | None = None,
        prompt_id: str | None = None,
        submission_state: str | None = None,
        outputs: list[OutputAsset] | None = None,
    ) -> None:
        if job_status is not None:
            record.status = job_status
        if error is not None:
            record.error = error[:1000]
        if prompt_id is not None:
            record.prompt_id = prompt_id
        if submission_state is not None:
            record.submission_state = submission_state
        if outputs is not None:
            record.outputs = outputs
        record.updated_at = _utc_now()
        self._persist(record)

    async def assert_comfy_ready(self, bundle: WorkflowBundle, checkpoint: str) -> None:
        response = await self.client.get(f"{self.config.comfy_url}/object_info")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise WorkerConfigurationError("ComfyUI object_info was not an object")
        missing = sorted(bundle.required_node_types.difference(payload))
        if missing:
            raise WorkerConfigurationError(
                "ComfyUI is missing required nodes: " + ", ".join(missing)
            )
        loader = payload.get("CheckpointLoaderSimple")
        installed = _checkpoint_options(loader)
        if installed and checkpoint not in installed:
            raise WorkerConfigurationError(
                f"checkpoint {checkpoint!r} is not installed"
            )

    async def execute(
        self,
        record: JobRecord,
        request: JobRequest,
        bundle: WorkflowBundle,
        checkpoint: str,
    ) -> None:
        async with self.execution_lock:
            if record.status is JobStatus.CANCEL_REQUESTED:
                self.update(record, job_status=JobStatus.CANCELLED)
                return
            self.update(record, job_status=JobStatus.RUNNING)
            try:
                await self.assert_comfy_ready(bundle, checkpoint)
                workflow = bundle.compile(request, checkpoint)
                try:
                    response = await self.client.post(
                        f"{self.config.comfy_url}/prompt",
                        json={"prompt": workflow},
                    )
                except httpx.RequestError as exc:
                    self.update(
                        record,
                        job_status=JobStatus.FAILED,
                        error=(
                            "submission outcome is unknown; request was not retried: "
                            f"{exc}"
                        ),
                        submission_state="unknown",
                    )
                    return
                if response.status_code >= 400:
                    self.update(
                        record,
                        job_status=JobStatus.FAILED,
                        error=(
                            f"ComfyUI rejected the workflow ({response.status_code}): "
                            f"{response.text[:500]}"
                        ),
                        submission_state="rejected",
                    )
                    return
                payload = response.json()
                prompt_id = (
                    str(payload.get("prompt_id"))
                    if isinstance(payload, Mapping) and payload.get("prompt_id")
                    else ""
                )
                if not prompt_id:
                    self.update(
                        record,
                        job_status=JobStatus.FAILED,
                        error="ComfyUI response did not include prompt_id",
                        submission_state="unknown",
                    )
                    return
                self.update(
                    record,
                    prompt_id=prompt_id,
                    submission_state="accepted",
                )
                assets = await self._wait_and_collect(record, bundle)
                if record.status is JobStatus.CANCEL_REQUESTED:
                    self.update(record, job_status=JobStatus.CANCELLED)
                    return
                self.update(
                    record,
                    job_status=JobStatus.SUCCEEDED,
                    outputs=assets,
                )
            except asyncio.CancelledError:
                self.update(record, job_status=JobStatus.CANCELLED)
                raise
            except (httpx.HTTPError, WorkerConfigurationError, ValueError) as exc:
                if record.status is JobStatus.CANCEL_REQUESTED:
                    self.update(record, job_status=JobStatus.CANCELLED)
                else:
                    self.update(
                        record,
                        job_status=JobStatus.FAILED,
                        error=str(exc),
                    )

    async def _wait_and_collect(
        self,
        record: JobRecord,
        bundle: WorkflowBundle,
    ) -> list[OutputAsset]:
        if not record.prompt_id:
            raise WorkerConfigurationError("job has no ComfyUI prompt id")
        deadline = time.monotonic() + self.config.generation_timeout_seconds
        while time.monotonic() < deadline:
            if record.status is JobStatus.CANCEL_REQUESTED:
                return []
            response = await self.client.get(
                f"{self.config.comfy_url}/history/{record.prompt_id}"
            )
            response.raise_for_status()
            payload = response.json()
            outputs = _history_outputs(
                payload, record.prompt_id, bundle.output_nodes
            )
            if outputs:
                return await self._download_outputs(record, outputs)
            await asyncio.sleep(self.config.poll_interval_seconds)
        raise WorkerConfigurationError("generation timed out")

    async def _download_outputs(
        self,
        record: JobRecord,
        outputs: Sequence[dict[str, str]],
    ) -> list[OutputAsset]:
        output_dir = self.config.job_root / record.job_id / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        assets: list[OutputAsset] = []
        for index, output in enumerate(outputs):
            response = await self.client.get(
                f"{self.config.comfy_url}/view",
                params={
                    "filename": output["filename"],
                    "subfolder": output["subfolder"],
                    "type": output["type"],
                },
            )
            response.raise_for_status()
            if not response.content:
                raise WorkerConfigurationError("ComfyUI returned an empty image")
            suffix = Path(output["filename"]).suffix.lower()
            if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
                suffix = ".png"
            asset_id = f"asset-{index + 1}"
            local_path = output_dir / f"{asset_id}{suffix}"
            local_path.write_bytes(response.content)
            digest = hashlib.sha256(response.content).hexdigest()
            media_type = _media_type_for_suffix(suffix)
            assets.append(
                OutputAsset(
                    asset_id=asset_id,
                    filename=local_path.name,
                    media_type=media_type,
                    size_bytes=len(response.content),
                    sha256=digest,
                    path=str(local_path),
                )
            )
        provenance_path = self.config.job_root / record.job_id / "provenance.json"
        provenance_path.write_text(
            json.dumps(
                {
                    "job_id": record.job_id,
                    "workflow_sha256": record.workflow_sha256,
                    "prompt_id": record.prompt_id,
                    "request": record.request,
                    "outputs": [asdict(item) for item in assets],
                    "generated_at": _utc_now(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return assets

    async def cancel(self, record: JobRecord) -> JobRecord:
        if record.status in TERMINAL_STATUSES:
            return record
        self.update(record, job_status=JobStatus.CANCEL_REQUESTED)
        try:
            response = await self.client.post(f"{self.config.comfy_url}/interrupt")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            self.update(
                record,
                error=f"cancellation requested but ComfyUI interrupt failed: {exc}",
            )
        task = self.tasks.get(record.job_id)
        if task is not None and not task.done():
            task.cancel()
        self.update(record, job_status=JobStatus.CANCELLED)
        return record


def create_app(
    config: WorkerConfig | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> FastAPI:
    worker_config = config or WorkerConfig.from_env()
    runtime = WorkerRuntime(worker_config, client=client)
    app = FastAPI(title="Kitty Comfy Worker", version="0.1.0")
    app.state.runtime = runtime

    async def require_auth(
        authorization: str | None = Header(default=None),
    ) -> None:
        expected = f"Bearer {worker_config.bearer_token}"
        if authorization is None or not hmac.compare_digest(
            authorization, expected
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    @app.middleware("http")
    async def request_size_limit(request: Request, call_next: Any) -> Any:
        raw_length = request.headers.get("content-length")
        if raw_length:
            try:
                length = int(raw_length)
            except ValueError:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "invalid content-length"},
                )
            if length > worker_config.max_request_bytes:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={"detail": "request body too large"},
                )
        return await call_next(request)

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await runtime.close()

    @app.get("/health")
    async def health() -> dict[str, object]:
        try:
            bundle = WorkflowBundle.load(
                worker_config.workflow_root, "text_to_image_v1"
            )
            await runtime.assert_comfy_ready(
                bundle, worker_config.default_checkpoint
            )
        except (WorkerConfigurationError, httpx.HTTPError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        return {
            "status": "ok",
            "comfy_url": worker_config.comfy_url,
            "workflows": [bundle.workflow_id],
            "default_checkpoint": worker_config.default_checkpoint,
        }

    @app.post(
        "/v1/jobs",
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=[Depends(require_auth)],
    )
    async def create_job(request: JobRequest) -> dict[str, Any]:
        try:
            bundle = WorkflowBundle.load(
                worker_config.workflow_root, request.workflow_id
            )
        except WorkerConfigurationError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        checkpoint = request.checkpoint or worker_config.default_checkpoint
        if checkpoint not in worker_config.allowed_checkpoints:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="checkpoint is not allowlisted",
            )
        job_id = str(uuid.uuid4())
        now = _utc_now()
        record = JobRecord(
            job_id=job_id,
            status=JobStatus.QUEUED,
            request=request.model_dump(),
            workflow_sha256=bundle.workflow_sha256,
            created_at=now,
            updated_at=now,
        )
        runtime.jobs[job_id] = record
        runtime._persist(record)
        task = asyncio.create_task(
            runtime.execute(record, request, bundle, checkpoint)
        )
        runtime.tasks[job_id] = task
        return record.public_dict()

    @app.get(
        "/v1/jobs/{job_id}",
        dependencies=[Depends(require_auth)],
    )
    async def get_job(job_id: str) -> dict[str, Any]:
        record = runtime.jobs.get(job_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="job not found",
            )
        return record.public_dict()

    @app.post(
        "/v1/jobs/{job_id}/cancel",
        dependencies=[Depends(require_auth)],
    )
    async def cancel_job(job_id: str) -> dict[str, Any]:
        record = runtime.jobs.get(job_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="job not found",
            )
        return (await runtime.cancel(record)).public_dict()

    @app.get(
        "/v1/jobs/{job_id}/outputs",
        dependencies=[Depends(require_auth)],
    )
    async def list_outputs(job_id: str) -> dict[str, Any]:
        record = runtime.jobs.get(job_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="job not found",
            )
        return {
            "job_id": job_id,
            "status": record.status.value,
            "outputs": record.public_dict()["outputs"],
        }

    @app.get(
        "/v1/jobs/{job_id}/outputs/{asset_id}",
        dependencies=[Depends(require_auth)],
    )
    async def download_output(job_id: str, asset_id: str) -> FileResponse:
        record = runtime.jobs.get(job_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="job not found",
            )
        asset = next(
            (item for item in record.outputs if item.asset_id == asset_id),
            None,
        )
        if asset is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="output not found",
            )
        path = Path(asset.path)
        expected_root = (worker_config.job_root / job_id / "outputs").resolve()
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(expected_root)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="output file unavailable",
            ) from exc
        return FileResponse(
            resolved,
            media_type=asset.media_type,
            filename=asset.filename,
        )

    return app


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise WorkerConfigurationError(f"{name} must be an integer") from exc


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise WorkerConfigurationError(f"{name} must be a number") from exc


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    if not isinstance(checkpoint, Sequence) or isinstance(
        checkpoint, (str, bytes)
    ):
        return set()
    if not checkpoint:
        return set()
    choices = checkpoint[0]
    if not isinstance(choices, Sequence) or isinstance(choices, (str, bytes)):
        return set()
    return {str(item) for item in choices}


def _history_outputs(
    payload: object,
    prompt_id: str,
    output_nodes: frozenset[str],
) -> list[dict[str, str]]:
    if not isinstance(payload, Mapping):
        raise WorkerConfigurationError("ComfyUI history response was invalid")
    raw_entry = payload.get(prompt_id)
    if raw_entry is None:
        return []
    if not isinstance(raw_entry, Mapping):
        raise WorkerConfigurationError("ComfyUI history entry was invalid")
    raw_status = raw_entry.get("status")
    if isinstance(raw_status, Mapping) and raw_status.get("status_str") in {
        "error",
        "failed",
    }:
        raise WorkerConfigurationError(
            f"ComfyUI execution failed: {raw_status.get('messages') or raw_status}"
        )
    raw_outputs = raw_entry.get("outputs")
    if not isinstance(raw_outputs, Mapping):
        return []
    found: list[dict[str, str]] = []
    for node_id in output_nodes:
        node_output = raw_outputs.get(node_id)
        if not isinstance(node_output, Mapping):
            continue
        images = node_output.get("images")
        if not isinstance(images, Sequence) or isinstance(images, (str, bytes)):
            continue
        for image in images:
            if not isinstance(image, Mapping) or not image.get("filename"):
                continue
            found.append(
                {
                    "filename": str(image["filename"]),
                    "subfolder": str(image.get("subfolder") or ""),
                    "type": str(image.get("type") or "output"),
                }
            )
    return found


def _media_type_for_suffix(suffix: str) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(suffix, "image/png")
