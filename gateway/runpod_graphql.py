"""Minimal RunPod GraphQL support for GPU Pod creation.

RunPod's current official CLI uses GraphQL for GPU Pod creation because the
GraphQL input supports cloud-enforced ``terminateAfter``. All other Kitty Pod
operations remain on the documented REST control plane.
"""

from __future__ import annotations

from typing import Any, Mapping, cast

import httpx

RUNPOD_GRAPHQL_URL = "https://api.runpod.io/graphql"

_CREATE_GPU_POD_MUTATION = """
mutation createPod($input: PodFindAndDeployOnDemandInput!) {
  podFindAndDeployOnDemand(input: $input) {
    id
    name
    desiredStatus
    costPerHr
    containerDiskInGb
    volumeInGb
    volumeMountPath
    gpuCount
    ports
    env
    machine {
      gpuDisplayName
      location
    }
  }
}
"""


class RunPodGraphQLError(RuntimeError):
    """Base class for RunPod GraphQL creation failures."""


class RunPodGraphQLRejectedError(RunPodGraphQLError):
    """RunPod definitively rejected a GraphQL mutation without a Pod result."""


class RunPodGraphQLAmbiguousError(RunPodGraphQLError):
    """A Pod may have been created but the response did not prove its outcome."""


async def create_gpu_pod(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    graphql_url: str,
    pod_input: Mapping[str, object],
) -> Mapping[str, Any]:
    """Create one GPU Pod without retrying an ambiguous mutation."""
    try:
        response = await client.post(
            graphql_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "query": _CREATE_GPU_POD_MUTATION,
                "variables": {"input": dict(pod_input)},
            },
        )
    except httpx.RequestError as exc:
        raise RunPodGraphQLAmbiguousError(
            f"GraphQL Pod creation lost transport confirmation: {exc}"
        ) from exc

    if response.status_code != 200:
        raise RunPodGraphQLAmbiguousError(
            "GraphQL Pod creation returned an inconclusive HTTP status "
            f"{response.status_code}: {response.text[:500]}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise RunPodGraphQLAmbiguousError(
            "GraphQL Pod creation returned invalid JSON"
        ) from exc
    if not isinstance(payload, Mapping):
        raise RunPodGraphQLAmbiguousError(
            "GraphQL Pod creation returned a non-object response"
        )

    data = payload.get("data")
    if isinstance(data, Mapping):
        pod = data.get("podFindAndDeployOnDemand")
        if isinstance(pod, Mapping) and pod.get("id"):
            return cast(Mapping[str, Any], pod)

    raw_errors = payload.get("errors")
    if isinstance(raw_errors, list) and raw_errors:
        messages: list[str] = []
        for item in raw_errors:
            if isinstance(item, Mapping) and item.get("message"):
                messages.append(str(item["message"]))
        detail = "; ".join(messages) if messages else "unknown GraphQL error"
        raise RunPodGraphQLRejectedError(detail[:1000])

    raise RunPodGraphQLAmbiguousError(
        "GraphQL Pod creation returned neither a Pod nor a rejection"
    )
