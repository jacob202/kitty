"""Client for the authenticated Kitty Comfy worker exposed by RunPod."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import httpx

from gateway.runpod_control import RunPodConfigurationError


class RunPodWorkerError(RuntimeError):
    """The Kitty worker returned an error or malformed response."""


class RunPodWorkerConfigurationError(RunPodConfigurationError):
    """The worker is reachable but cannot run the installed workflow."""


class RunPodWorkerAmbiguousSubmissionError(RunPodWorkerError):
    """The worker may have accepted the job; callers must not retry blindly."""


def _as_int(value: object, default: int = 0) -> int:
    if not isinstance(value, (int, str)) or isinstance(value, bool):
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class WorkerOutput:
    asset_id: str
    filename: str
    media_type: str
    size_bytes: int
    sha256: str
    download_url: str
    width: int
    height: int

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "WorkerOutput":
        return cls(
            asset_id=str(payload.get("asset_id") or ""),
            filename=str(payload.get("filename") or ""),
            media_type=str(payload.get("media_type") or "application/octet-stream"),
            size_bytes=_as_int(payload.get("size_bytes")),
            sha256=str(payload.get("sha256") or ""),
            download_url=str(payload.get("download_url") or ""),
            width=_as_int(payload.get("width")),
            height=_as_int(payload.get("height")),
        )


@dataclass(frozen=True)
class WorkerJob:
    job_id: str
    status: str
    workflow_sha256: str
    prompt_id: str | None
    submission_state: str
    error: str | None
    outputs: tuple[WorkerOutput, ...]

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "WorkerJob":
        raw_outputs = payload.get("outputs")
        outputs: list[WorkerOutput] = []
        if isinstance(raw_outputs, Sequence) and not isinstance(
            raw_outputs, (str, bytes)
        ):
            outputs = [
                WorkerOutput.from_payload(item)
                for item in raw_outputs
                if isinstance(item, Mapping)
            ]
        return cls(
            job_id=str(payload.get("job_id") or ""),
            status=str(payload.get("status") or "unknown"),
            workflow_sha256=str(payload.get("workflow_sha256") or ""),
            prompt_id=(
                str(payload["prompt_id"]) if payload.get("prompt_id") else None
            ),
            submission_state=str(
                payload.get("submission_state") or "not_submitted"
            ),
            error=str(payload["error"]) if payload.get("error") else None,
            outputs=tuple(outputs),
        )


class RunPodWorkerClient:
    """Narrow asynchronous client for one Kitty worker instance."""

    def __init__(
        self,
        base_url: str,
        bearer_token: str,
        *,
        timeout_seconds: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not base_url.strip():
            raise RunPodWorkerError("worker base URL is required")
        if not bearer_token.strip():
            raise RunPodWorkerError("worker bearer token is required")
        self._base_url = base_url.rstrip("/")
        self._token = bearer_token.strip()
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    async def __aenter__(self) -> "RunPodWorkerClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def assert_ready(self) -> dict[str, Any]:
        response = await self._client.get(f"{self._base_url}/health")
        if response.status_code == 424:
            raise RunPodWorkerConfigurationError(
                _health_error_message(response)
            )
        if response.status_code >= 400:
            raise RunPodWorkerError(
                f"worker health returned {response.status_code}: "
                f"{response.text[:500]}"
            )
        payload = response.json()
        if not isinstance(payload, Mapping) or payload.get("status") != "ok":
            raise RunPodWorkerError("worker health response was malformed")
        return dict(payload)

    async def submit(
        self,
        *,
        workflow_id: str,
        prompt: str,
        negative_prompt: str,
        checkpoint: str,
        width: int,
        height: int,
        steps: int,
        guidance: float,
        seed: int,
        client_action_id: str | None = None,
    ) -> WorkerJob:
        try:
            response = await self._client.post(
                f"{self._base_url}/v1/jobs",
                headers=self._headers,
                json={
                    "workflow_id": workflow_id,
                    "prompt": prompt,
                    "negative_prompt": negative_prompt,
                    "checkpoint": checkpoint,
                    "width": width,
                    "height": height,
                    "steps": steps,
                    "guidance": guidance,
                    "seed": seed,
                    "count": 1,
                    "client_action_id": client_action_id,
                },
            )
        except httpx.RequestError as exc:
            raise RunPodWorkerAmbiguousSubmissionError(
                "connection failed while submitting to the worker; the job may "
                "have been accepted, so Kitty will not retry automatically"
            ) from exc
        if response.status_code >= 400:
            raise RunPodWorkerError(
                f"worker rejected the job ({response.status_code}): "
                f"{response.text[:500]}"
            )
        return _parse_job(response.json())

    async def get_job(self, job_id: str) -> WorkerJob:
        response = await self._client.get(
            f"{self._base_url}/v1/jobs/{job_id}",
            headers=self._headers,
        )
        if response.status_code >= 400:
            raise RunPodWorkerError(
                f"worker job status returned {response.status_code}: "
                f"{response.text[:500]}"
            )
        return _parse_job(response.json())

    async def wait(
        self,
        job_id: str,
        *,
        timeout_seconds: int,
        poll_interval_seconds: float,
    ) -> WorkerJob:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            job = await self.get_job(job_id)
            if job.status == "succeeded":
                return job
            if job.status in {"failed", "cancelled"}:
                raise RunPodWorkerError(
                    f"worker job {job_id} ended as {job.status}: "
                    f"{job.error or 'no error detail'}"
                )
            await asyncio.sleep(poll_interval_seconds)
        raise RunPodWorkerError(
            f"worker job {job_id} did not finish within {timeout_seconds}s"
        )

    async def cancel(self, job_id: str) -> WorkerJob:
        response = await self._client.post(
            f"{self._base_url}/v1/jobs/{job_id}/cancel",
            headers=self._headers,
        )
        if response.status_code >= 400:
            raise RunPodWorkerError(
                f"worker cancellation returned {response.status_code}: "
                f"{response.text[:500]}"
            )
        return _parse_job(response.json())

    async def download(self, output: WorkerOutput) -> bytes:
        if not output.download_url.startswith("/"):
            raise RunPodWorkerError("worker returned an invalid download URL")
        response = await self._client.get(
            f"{self._base_url}{output.download_url}",
            headers=self._headers,
        )
        if response.status_code >= 400:
            raise RunPodWorkerError(
                f"worker output download returned {response.status_code}: "
                f"{response.text[:500]}"
            )
        if not response.content:
            raise RunPodWorkerError("worker returned an empty output")
        return response.content


def _health_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"worker configuration failed: {response.text[:500]}"
    if not isinstance(payload, Mapping):
        return "worker configuration failed"
    detail = payload.get("detail")
    if isinstance(detail, Mapping) and detail.get("message"):
        return str(detail["message"])
    return f"worker configuration failed: {response.text[:500]}"


def _parse_job(payload: object) -> WorkerJob:
    if not isinstance(payload, Mapping):
        raise RunPodWorkerError("worker job response was not an object")
    job = WorkerJob.from_payload(payload)
    if not job.job_id:
        raise RunPodWorkerError("worker job response did not include job_id")
    return job
