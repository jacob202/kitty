"""Narrow RunPod control-plane client for Kitty-managed image Pods.

GPU Pod creation uses RunPod's GraphQL mutation because that API supports the
cloud-enforced ``terminateAfter`` deadline used by the official RunPod CLI.
Listing, inspection, deletion, and billing continue to use the REST API.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence, cast

import httpx

from gateway.runpod_graphql import (
    RUNPOD_GRAPHQL_URL,
    RunPodGraphQLAmbiguousError,
    RunPodGraphQLRejectedError,
    create_gpu_pod,
)

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
    """A REST request lost transport-level confirmation of its outcome."""


class RunPodAmbiguousCreateError(RunPodApiError):
    """RunPod may have created a billable Pod despite an inconclusive result."""

    def __init__(self, pod_name: str, cause: BaseException) -> None:
        self.pod_name = pod_name
        super().__init__(
            "RunPod Pod creation outcome is unknown; reconcile Pod name "
            f"{pod_name!r} before retrying: {cause}"
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
    """Minimal asynchronous RunPod client for ephemeral image Pods."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = RUNPOD_API_BASE,
        graphql_url: str = RUNPOD_GRAPHQL_URL,
        timeout_seconds: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key.strip():
            raise RunPodConfigurationError("RUNPOD_API_KEY is required")
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._graphql_url = graphql_url
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
        image_name: str | None = None,
        container_start_cmd: str | None = None,
    ) -> PodInfo:
        if not template_id.strip():
            raise RunPodConfigurationError("RUNPOD_TEMPLATE_ID is required")
        normalized_gpu_ids = [item.strip() for item in gpu_type_ids if item.strip()]
        if not normalized_gpu_ids:
            raise RunPodConfigurationError("at least one GPU type ID is required")
        if cloud_type not in {"COMMUNITY", "SECURE"}:
            raise RunPodConfigurationError("cloud_type must be COMMUNITY or SECURE")
        if not math.isfinite(max_hourly_rate) or max_hourly_rate <= 0:
            raise RunPodConfigurationError(
                "max_hourly_rate must be positive and finite"
            )
        if hard_runtime_minutes <= 0:
            raise RunPodConfigurationError("hard_runtime_minutes must be positive")

        now = datetime.now(timezone.utc)
        expires_at = datetime.fromtimestamp(
            now.timestamp() + hard_runtime_minutes * 60,
            tz=timezone.utc,
        )
        expires_at_rfc3339 = expires_at.isoformat().replace("+00:00", "Z")
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

        if image_name is not None:
            normalized_image_name = image_name.strip()
            normalized_container_start_cmd = (
                container_start_cmd.strip()
                if container_start_cmd
                else ""
            )
            if not normalized_image_name:
                raise RunPodConfigurationError("image_name must not be empty")
            if not normalized_container_start_cmd:
                raise RunPodConfigurationError(
                    "explicit REST deployment requires container_start_cmd"
                )
            return await self._create_image_pod_rest(
                template_id=template_id,
                image_name=normalized_image_name,
                container_start_cmd=normalized_container_start_cmd,
                gpu_type_ids=normalized_gpu_ids,
                max_hourly_rate=max_hourly_rate,
                ports=ports,
                network_volume_id=network_volume_id,
                cloud_type=cloud_type,
                container_disk_gb=container_disk_gb,
                volume_gb=volume_gb,
                pod_env=pod_env,
                pod_name=pod_name,
            )
        if container_start_cmd is not None:
            raise RunPodConfigurationError(
                "container_start_cmd requires image_name and REST deployment"
            )

        common_input: dict[str, object] = {
            "name": pod_name,
            "cloudType": cloud_type,
            "containerDiskInGb": container_disk_gb,
            "env": [
                {"key": key, "value": value}
                for key, value in sorted(pod_env.items())
            ],
            "gpuCount": 1,
            "ports": ",".join(ports),
            "startSsh": False,
            "supportPublicIp": False,
            "templateId": template_id,
            "terminateAfter": expires_at_rfc3339,
            "volumeMountPath": "/workspace",
        }
        if network_volume_id:
            common_input["networkVolumeId"] = network_volume_id
        else:
            common_input["volumeInGb"] = volume_gb

        rejections: list[str] = []
        for gpu_type_id in normalized_gpu_ids:
            pod_input = dict(common_input)
            pod_input["gpuTypeId"] = gpu_type_id
            try:
                payload = await create_gpu_pod(
                    self._client,
                    api_key=self._api_key,
                    graphql_url=self._graphql_url,
                    pod_input=pod_input,
                )
            except RunPodGraphQLRejectedError as exc:
                rejections.append(f"{gpu_type_id}: {exc}")
                continue
            except RunPodGraphQLAmbiguousError as exc:
                raise RunPodAmbiguousCreateError(pod_name, exc) from exc

            normalized_payload = dict(payload)
            normalized_payload.setdefault("name", pod_name)
            normalized_payload["env"] = pod_env
            pod = PodInfo.from_payload(normalized_payload)
            if not pod.pod_id:
                raise RunPodAmbiguousCreateError(
                    pod_name,
                    RunPodApiError(
                        "GraphQL create result did not include a Pod id"
                    ),
                )
            await self._validate_created_pod_rate(pod, max_hourly_rate)
            return pod

        details = "; ".join(rejections) or "no GPU candidates were attempted"
        raise RunPodApiError(
            "RunPod rejected every requested GPU candidate: " + details
        )

    async def _create_image_pod_rest(
        self,
        *,
        template_id: str,
        image_name: str,
        container_start_cmd: str,
        gpu_type_ids: Sequence[str],
        max_hourly_rate: float,
        ports: Sequence[str],
        network_volume_id: str | None,
        cloud_type: str,
        container_disk_gb: int,
        volume_gb: int,
        pod_env: Mapping[str, str],
        pod_name: str,
    ) -> PodInfo:
        pod_input: dict[str, object] = {
            "name": pod_name,
            "cloudType": cloud_type,
            "computeType": "GPU",
            "containerDiskInGb": container_disk_gb,
            "dockerEntrypoint": ["/bin/sh", "-c"],
            "dockerStartCmd": [container_start_cmd],
            "env": dict(sorted(pod_env.items())),
            "gpuCount": 1,
            "gpuTypeIds": list(gpu_type_ids),
            "gpuTypePriority": "custom",
            "imageName": image_name,
            "interruptible": False,
            "locked": False,
            "ports": list(ports),
            "supportPublicIp": False,
            "volumeMountPath": "/workspace",
        }
        if network_volume_id:
            pod_input["networkVolumeId"] = network_volume_id
        else:
            pod_input["volumeInGb"] = volume_gb

        try:
            payload = await self._request("POST", "/pods", json_body=pod_input)
        except RunPodTransportError as exc:
            raise RunPodAmbiguousCreateError(pod_name, exc) from exc
        except RunPodApiError as exc:
            message = str(exc)
            lowered = message.lower()
            capacity_markers = (
                "no capacity",
                "no available",
                "not available",
                "availability",
                "unable to rent",
                "could not find",
            )
            if any(marker in lowered for marker in capacity_markers):
                raise RunPodApiError(
                    "RunPod rejected every requested GPU candidate: " + message
                ) from exc
            raise

        if not isinstance(payload, Mapping):
            raise RunPodAmbiguousCreateError(
                pod_name, RunPodApiError("REST create result was not an object")
            )
        normalized_payload = dict(payload)
        normalized_payload.setdefault("name", pod_name)
        normalized_payload.setdefault("env", dict(pod_env))
        pod = PodInfo.from_payload(normalized_payload)
        if not pod.pod_id:
            raise RunPodAmbiguousCreateError(
                pod_name, RunPodApiError("REST create result did not include a Pod id")
            )

        await self._validate_created_pod_rate(pod, max_hourly_rate)
        return pod

    async def _validate_created_pod_rate(
        self,
        pod: PodInfo,
        max_hourly_rate: float,
    ) -> None:
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
        if pod.hourly_rate <= max_hourly_rate:
            return
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

    async def pod_logs(self, pod_id: str) -> str:
        """Return the Pod's container output, or an explanation of why not.

        Diagnostic only, so it reports transport and API failures as text
        instead of raising: it runs inside failure handling, where masking the
        original error would be worse than losing the logs. When the worker
        never binds its port there is nothing HTTP-reachable left to ask, and
        this is the only view into why the container start command died.
        """
        if not pod_id.strip():
            return "(no pod id)"
        try:
            payload = await self._request("GET", f"/pods/{pod_id}/logs")
        except RunPodError as exc:
            return f"(could not fetch Pod logs: {exc})"

        if isinstance(payload, str):
            return payload
        if isinstance(payload, Mapping):
            for key in ("logs", "output", "container", "data"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value
        return f"(unrecognized Pod log payload: {str(payload)[:300]})"

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
