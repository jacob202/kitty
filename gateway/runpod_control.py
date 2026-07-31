"""Narrow RunPod control-plane client for Kitty-managed image Pods.

This module intentionally covers only the Pod lifecycle needed by the first
Image Studio smoke test. It does not expose a generic RunPod SDK surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

RUNPOD_API_BASE = "https://rest.runpod.io/v1"
KITTY_POD_PREFIX = "kitty-image-"


class RunPodError(RuntimeError):
    """Base class for RunPod control-plane failures."""


class RunPodConfigurationError(RunPodError):
    """Required local configuration is missing or invalid."""


class RunPodApiError(RunPodError):
    """RunPod returned an unsuccessful response."""


class RunPodBudgetError(RunPodError):
    """A created Pod exceeded the configured hourly ceiling."""


def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class PodInfo:
    pod_id: str
    name: str
    desired_status: str
    gpu_name: str
    hourly_rate: float
    created_at: str | None
    env: dict[str, str]
    raw: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "PodInfo":
        gpu = payload.get("gpu") if isinstance(payload.get("gpu"), dict) else {}
        env = payload.get("env") if isinstance(payload.get("env"), dict) else {}
        hourly_rate = _float(payload.get("adjustedCostPerHr")) or _float(
            payload.get("costPerHr")
        )
        return cls(
            pod_id=str(payload.get("id") or ""),
            name=str(payload.get("name") or ""),
            desired_status=str(payload.get("desiredStatus") or "UNKNOWN"),
            gpu_name=str(gpu.get("displayName") or gpu.get("id") or "unknown"),
            hourly_rate=hourly_rate,
            created_at=(
                str(payload.get("lastStartedAt")) if payload.get("lastStartedAt") else None
            ),
            env={str(k): str(v) for k, v in env.items()},
            raw=payload,
        )

    @property
    def worker_url(self) -> str:
        return f"https://{self.pod_id}-8000.proxy.runpod.net"


class RunPodControlClient:
    """Minimal asynchronous client for Kitty's ephemeral image Pods."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = RUNPOD_API_BASE,
        timeout_seconds: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key.strip():
            raise RunPodConfigurationError("RUNPOD_API_KEY is required")
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    async def __aenter__(self) -> "RunPodControlClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, object] | None = None,
        json: dict[str, object] | None = None,
        allow_no_content: bool = False,
    ) -> Any:
        try:
            response = await self._client.request(
                method,
                f"{self._base_url}{path}",
                headers=self._headers,
                params=params,
                json=json,
            )
        except httpx.RequestError as exc:
            raise RunPodApiError(f"RunPod request failed before a response: {exc}") from exc

        if response.status_code >= 400:
            body = response.text[:500]
            raise RunPodApiError(
                f"RunPod {method} {path} returned {response.status_code}: {body}"
            )
        if allow_no_content and response.status_code == 204:
            return None
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise RunPodApiError(
                f"RunPod {method} {path} returned invalid JSON"
            ) from exc

    async def list_pods(self) -> list[PodInfo]:
        payload = await self._request("GET", "/pods")
        if not isinstance(payload, list):
            raise RunPodApiError("RunPod list Pods response was not a list")
        return [PodInfo.from_payload(item) for item in payload if isinstance(item, dict)]

    async def list_managed_pods(self) -> list[PodInfo]:
        return [pod for pod in await self.list_pods() if pod.name.startswith(KITTY_POD_PREFIX)]

    async def get_pod(self, pod_id: str) -> PodInfo:
        payload = await self._request(
            "GET",
            f"/pods/{pod_id}",
            params={"includeMachine": True, "includeNetworkVolume": True},
        )
        if not isinstance(payload, dict):
            raise RunPodApiError("RunPod Pod response was not an object")
        return PodInfo.from_payload(payload)

    async def create_image_pod(
        self,
        *,
        template_id: str,
        worker_token: str,
        network_volume_id: str | None,
        gpu_type_ids: list[str],
        max_hourly_rate: float,
        hard_runtime_minutes: int,
        cloud_type: str = "COMMUNITY",
        name_suffix: str | None = None,
    ) -> PodInfo:
        if not template_id.strip():
            raise RunPodConfigurationError("RUNPOD_TEMPLATE_ID is required")
        if not worker_token.strip():
            raise RunPodConfigurationError("KITTY_WORKER_BEARER_TOKEN is required")
        if not gpu_type_ids:
            raise RunPodConfigurationError("At least one RunPod GPU type ID is required")
        if cloud_type not in {"COMMUNITY", "SECURE"}:
            raise RunPodConfigurationError("cloud_type must be COMMUNITY or SECURE")

        now = datetime.now(timezone.utc)
        expires_at = now.timestamp() + hard_runtime_minutes * 60
        suffix = name_suffix or now.strftime("%Y%m%d-%H%M%S")
        body: dict[str, object] = {
            "name": f"{KITTY_POD_PREFIX}{suffix}",
            "cloudType": cloud_type,
            "computeType": "GPU",
            "gpuCount": 1,
            "gpuTypeIds": gpu_type_ids,
            "gpuTypePriority": "availability",
            "templateId": template_id,
            "ports": ["8000/http"],
            "globalNetworking": True,
            "supportPublicIp": True,
            "interruptible": False,
            "locked": False,
            "volumeMountPath": "/workspace",
            "env": {
                "KITTY_MANAGED": "1",
                "KITTY_WORKER_BEARER_TOKEN": worker_token,
                "KITTY_SESSION_EXPIRES_AT": datetime.fromtimestamp(
                    expires_at, tz=timezone.utc
                ).isoformat(),
            },
        }
        if network_volume_id:
            body["networkVolumeId"] = network_volume_id

        payload = await self._request("POST", "/pods", json=body)
        if not isinstance(payload, dict):
            raise RunPodApiError("RunPod create Pod response was not an object")
        pod = PodInfo.from_payload(payload)
        if not pod.pod_id:
            raise RunPodApiError("RunPod create Pod response did not include an id")
        if pod.hourly_rate and pod.hourly_rate > max_hourly_rate:
            await self.delete_pod(pod.pod_id)
            raise RunPodBudgetError(
                f"Created Pod rate ${pod.hourly_rate:.3f}/hr exceeds "
                f"the ${max_hourly_rate:.3f}/hr ceiling; Pod was terminated"
            )
        return pod

    async def delete_pod(self, pod_id: str) -> None:
        await self._request("DELETE", f"/pods/{pod_id}", allow_no_content=True)

    async def pod_billing(self, pod_id: str) -> list[dict[str, Any]]:
        payload = await self._request(
            "GET",
            "/billing/pods",
            params={"bucketSize": "hour", "podId": pod_id, "grouping": "podId"},
        )
        if not isinstance(payload, list):
            raise RunPodApiError("RunPod billing response was not a list")
        return [item for item in payload if isinstance(item, dict)]

    async def actual_cost(self, pod_id: str) -> float | None:
        records = await self.pod_billing(pod_id)
        matching = [item for item in records if str(item.get("podId")) == pod_id]
        if not matching:
            return None
        return sum(_float(item.get("amount")) for item in matching)
