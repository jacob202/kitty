"""Narrow RunPod control-plane client for Kitty-managed image Pods.

This module intentionally covers only the Pod lifecycle required by the first
Image Studio smoke test. It is not a generic RunPod SDK.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence, cast

import httpx

RUNPOD_API_BASE = "https://rest.runpod.io/v1"
KITTY_POD_PREFIX = "kitty-image-"
_RESERVED_ENV_KEYS = frozenset(
    {
        "KITTY_MANAGED",
        "KITTY_SESSION_EXPIRES_AT",
    }
)


class RunPodError(RuntimeError):
    """Base class for RunPod control-plane failures."""


class RunPodConfigurationError(RunPodError):
    """Required local configuration is missing or invalid."""


class RunPodApiError(RunPodError):
    """RunPod returned an unsuccessful or malformed response."""


class RunPodTransportError(RunPodApiError):
    """A request lost transport-level confirmation of its outcome."""


class RunPodAmbiguousCreateError(RunPodApiError):
    """RunPod may have created a billable Pod despite a lost response."""

    def __init__(self, pod_name: str, cause: BaseException) -> None:
        self.pod_name = pod_name
        super().__init__(
            "RunPod Pod creation outcome is unknown after a transport failure; "
            f"reconcile Pod name {pod_name!r} before retrying: {cause}"
        )


class RunPodBudgetError(RunPodError):
    """A created Pod exceeded the configured hourly ceiling."""


def _finite_float(value: object, *, allow_zero: bool) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    if not math.isfinite(parsed):
        return None
    if parsed < 0 or (parsed == 0 and not allow_zero):
        return None
    return parsed


def _as_mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return cast(Mapping[str, Any], value)


@dataclass(frozen=True)
class PodInfo:
    """Normalized subset of RunPod's Pod response."""

    pod_id: str
    name: str
    desired_status: str
    gpu_name: str
    hourly_rate: float
    created_at: str | None
    env: dict[str, str]
    raw: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "PodInfo":
        gpu = _as_mapping(payload.get("gpu"))
        machine = _as_mapping(payload.get("machine"))
        env = _as_mapping(payload.get("env"))
        rate = _finite_float(
            payload.get("adjustedCostPerHr"), allow_zero=False
        ) or _finite_float(payload.get("costPerHr"), allow_zero=False)
        gpu_name = (
            gpu.get("displayName")
            or gpu.get("id")
            or machine.get("gpuDisplayName")
            or "unknown"
        )
        created_at_raw = payload.get("lastStartedAt") or payload.get("createdAt")
        return cls(
            pod_id=str(payload.get("id") or ""),
            name=str(payload.get("name") or ""),
            desired_status=str(payload.get("desiredStatus") or "UNKNOWN"),
            gpu_name=str(gpu_name),
            hourly_rate=rate or 0.0,
            created_at=str(created_at_raw) if created_at_raw else None,
            env={str(key): str(value) for key, value in env.items()},
            raw=dict(payload),
        )

    def proxy_url(self, port: int) -> str:
        if not self.pod_id:
            raise RunPodApiError("cannot build proxy URL for a Pod without an id")
        if port <= 0 or port > 65535:
            raise RunPodConfigurationError(f"invalid proxy port: {port}")
        return f"https://{self.pod_id}-{port}.proxy.runpod.net"

    def expiry(self) -> datetime | None:
        value = self.env.get("KITTY_SESSION_EXPIRES_AT")
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def is_expired(self, *, now: datetime | None = None) -> bool:
        expiry = self.expiry()
        if expiry is None:
            return False
        current = now or datetime.now(timezone.utc)
        return current >= expiry

    def is_managed(self) -> bool:
        return self.name.startswith(KITTY_POD_PREFIX) and self.env.get(
            "KITTY_MANAGED"
        ) == "1"


class RunPodControlClient:
    """Minimal asynchronous RunPod REST client for ephemeral image Pods."""

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
        params: Mapping[str, object] | None = None,
        json_body: Mapping[str, object] | None = None,
        allow_no_content: bool = False,
    ) -> Any:
        try:
            response = await self._client.request(
                method,
                f"{self._base_url}{path}",
                headers=self._headers,
                params=params,
                json=dict(json_body) if json_body is not None else None,
            )
        except httpx.RequestError as exc:
            raise RunPodTransportError(
                f"RunPod {method} {path} lost transport confirmation: {exc}"
            ) from exc

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
        return [
            PodInfo.from_payload(item)
            for item in payload
            if isinstance(item, Mapping)
        ]

    async def list_managed_pods(self) -> list[PodInfo]:
        return [pod for pod in await self.list_pods() if pod.is_managed()]

    async def get_pod(self, pod_id: str) -> PodInfo:
        if not pod_id.strip():
            raise RunPodConfigurationError("pod_id is required")
        payload = await self._request(
            "GET",
            f"/pods/{pod_id}",
            params={"includeMachine": True, "includeNetworkVolume": True},
        )
        if not isinstance(payload, Mapping):
            raise RunPodApiError("RunPod Pod response was not an object")
        pod = PodInfo.from_payload(payload)
        if not pod.pod_id:
            raise RunPodApiError("RunPod Pod response did not include an id")
        return pod

    async def create_image_pod(
        self,
        *,
        template_id: str,
        gpu_type_ids: Sequence[str],
        max_hourly_rate: float,
        hard_runtime_minutes: int,
        ports: Sequence[str] = ("8000/http",),
        network_volume_id: str | None = None,
        cloud_type: str = "COMMUNITY",
        container_disk_gb: int = 30,
        volume_gb: int = 20,
        env: Mapping[str, str] | None = None,
        name_suffix: str | None = None,
    ) -> PodInfo:
        if not template_id.strip():
            raise RunPodConfigurationError("RUNPOD_TEMPLATE_ID is required")
        normalized_gpu_ids = [item.strip() for item in gpu_type_ids if item.strip()]
        if not normalized_gpu_ids:
            raise RunPodConfigurationError("at least one GPU type ID is required")
        if cloud_type not in {"COMMUNITY", "SECURE"}:
            raise RunPodConfigurationError("cloud_type must be COMMUNITY or SECURE")
        if not math.isfinite(max_hourly_rate) or max_hourly_rate <= 0:
            raise RunPodConfigurationError("max_hourly_rate must be positive and finite")
        if hard_runtime_minutes <= 0:
            raise RunPodConfigurationError("hard_runtime_minutes must be positive")

        now = datetime.now(timezone.utc)
        expires_at = datetime.fromtimestamp(
            now.timestamp() + hard_runtime_minutes * 60,
            tz=timezone.utc,
        )
        pod_env = {
            str(key): str(value)
            for key, value in (env or {}).items()
            if str(key) not in _RESERVED_ENV_KEYS
        }
        pod_env.update(
            {
                "KITTY_MANAGED": "1",
                "KITTY_SESSION_EXPIRES_AT": expires_at.isoformat(),
            }
        )

        suffix = name_suffix or now.strftime("%Y%m%d-%H%M%S")
        pod_name = f"{KITTY_POD_PREFIX}{suffix}"
        body: dict[str, object] = {
            "name": pod_name,
            "cloudType": cloud_type,
            "computeType": "GPU",
            "gpuCount": 1,
            "gpuTypeIds": normalized_gpu_ids,
            "gpuTypePriority": "availability",
            "templateId": template_id,
            "ports": list(ports),
            "interruptible": False,
            "locked": False,
            "containerDiskInGb": container_disk_gb,
            "volumeMountPath": "/workspace",
            "env": pod_env,
        }
        if network_volume_id:
            body["networkVolumeId"] = network_volume_id
        else:
            body["volumeInGb"] = volume_gb

        try:
            payload = await self._request("POST", "/pods", json_body=body)
        except RunPodTransportError as exc:
            raise RunPodAmbiguousCreateError(pod_name, exc) from exc
        if not isinstance(payload, Mapping):
            raise RunPodApiError("RunPod create Pod response was not an object")
        pod = PodInfo.from_payload(payload)
        if not pod.pod_id:
            raise RunPodApiError("RunPod create Pod response did not include an id")
        if pod.hourly_rate <= 0:
            cleanup_error = await self._delete_after_invalid_create(pod.pod_id)
            detail = (
                f"; cleanup failed: {cleanup_error}"
                if cleanup_error is not None
                else "; Pod was terminated"
            )
            raise RunPodApiError(
                "RunPod create response omitted a positive finite hourly rate" + detail
            )
        if pod.hourly_rate > max_hourly_rate:
            cleanup_error = await self._delete_after_invalid_create(pod.pod_id)
            if cleanup_error is not None:
                raise RunPodBudgetError(
                    f"created Pod rate ${pod.hourly_rate:.3f}/hr exceeds the "
                    f"${max_hourly_rate:.3f}/hr ceiling; cleanup failed: "
                    f"{cleanup_error}"
                )
            raise RunPodBudgetError(
                f"created Pod rate ${pod.hourly_rate:.3f}/hr exceeds "
                f"the ${max_hourly_rate:.3f}/hr ceiling; Pod was terminated"
            )
        return pod

    async def _delete_after_invalid_create(self, pod_id: str) -> str | None:
        try:
            await self.delete_pod(pod_id)
        except RunPodApiError as exc:
            return str(exc)
        return None

    async def delete_pod(self, pod_id: str) -> None:
        if not pod_id.strip():
            raise RunPodConfigurationError("pod_id is required")
        await self._request(
            "DELETE",
            f"/pods/{pod_id}",
            allow_no_content=True,
        )

    async def pod_billing(self, pod_id: str) -> list[dict[str, Any]]:
        payload = await self._request(
            "GET",
            "/billing/pods",
            params={"bucketSize": "hour", "podId": pod_id, "grouping": "podId"},
        )
        if not isinstance(payload, list):
            raise RunPodApiError("RunPod billing response was not a list")
        return [dict(item) for item in payload if isinstance(item, Mapping)]

    async def actual_cost(self, pod_id: str) -> float | None:
        records = await self.pod_billing(pod_id)
        matching = [
            item
            for item in records
            if not item.get("podId") or str(item.get("podId")) == pod_id
        ]
        if not matching:
            return None
        total = 0.0
        found = False
        for item in matching:
            for key in ("amount", "cost", "totalCost"):
                if key not in item or item.get(key) is None:
                    continue
                amount = _finite_float(item.get(key), allow_zero=True)
                if amount is None:
                    raise RunPodApiError(
                        f"RunPod billing record contained invalid {key!r} value"
                    )
                total += amount
                found = True
                break
        return total if found else None
