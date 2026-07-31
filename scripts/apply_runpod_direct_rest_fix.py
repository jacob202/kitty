from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def patch_control() -> None:
    path = Path("gateway/runpod_control.py")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        """                pod_env=pod_env,
                pod_name=pod_name,
                terminate_after=expires_at_rfc3339,
            )
""",
        """                pod_env=pod_env,
                pod_name=pod_name,
            )
""",
        "control caller",
    )
    start = text.index("    async def _create_image_pod_rest(")
    end = text.index("    async def _validate_created_pod_rate(", start)
    method = '''    async def _create_image_pod_rest(
        self,
        *,
        template_id: str,
        image_name: str,
        docker_entrypoint: Sequence[str],
        docker_start_cmd: Sequence[str],
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
        # A Pod created from a template can report updated startup fields while the
        # running container continues using the template's original command. Create
        # directly from the image so RunPod applies ENTRYPOINT/CMD at first launch.
        pod_input: dict[str, object] = {
            "name": pod_name,
            "cloudType": cloud_type,
            "computeType": "GPU",
            "containerDiskInGb": container_disk_gb,
            "dockerEntrypoint": list(docker_entrypoint),
            "dockerStartCmd": list(docker_start_cmd),
            "env": dict(sorted(pod_env.items())),
            "gpuCount": 1,
            "gpuTypeIds": list(gpu_type_ids),
            "gpuTypePriority": "custom",
            "imageName": image_name,
            "interruptible": False,
            "locked": False,
            "ports": list(ports),
            "supportPublicIp": False,
            "templateId": None,
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

        observed_entrypoint = normalized_payload.get("dockerEntrypoint")
        observed_start_cmd = normalized_payload.get("dockerStartCmd")
        if (
            observed_entrypoint != list(docker_entrypoint)
            or observed_start_cmd != list(docker_start_cmd)
        ):
            cleanup_error = await self._delete_after_invalid_create(pod.pod_id)
            detail = (
                f"; cleanup failed: {cleanup_error}"
                if cleanup_error is not None
                else "; Pod was terminated"
            )
            raise RunPodApiError(
                "RunPod direct create did not preserve explicit Docker startup overrides"
                + detail
            )

        await self._validate_created_pod_rate(pod, max_hourly_rate)
        return pod

'''
    path.write_text(text[:start] + method + text[end:], encoding="utf-8")


def patch_batch() -> None:
    path = Path("scripts/runpod_james_batch.py")
    text = path.read_text(encoding="utf-8")
    start = text.index("async def _create_temporary_template(")
    end = text.index("async def _wait_for_pod(", start)
    helper = '''async def _direct_deployment_config(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    source_template_id: str,
    bootstrap_ref: str,
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    source = await _template_request(
        client,
        api_key,
        "GET",
        f"/templates/{source_template_id}",
        params={"includePublicTemplates": True, "includeRunpodTemplates": True},
    )
    if not isinstance(source, Mapping):
        raise RuntimeError("RunPod source template response was not an object")
    image_name = str(source.get("imageName") or "").strip()
    if not image_name:
        raise RuntimeError("RunPod source template did not include imageName")

    bootstrap_url = (
        "https://raw.githubusercontent.com/jacob202/kitty/"
        f"{bootstrap_ref}/workers/comfy_worker/bootstrap.sh"
    )
    command = (
        "python -c \\\"import urllib.request; "
        "open('/tmp/kitty-bootstrap.sh','wb').write("
        f"urllib.request.urlopen('{bootstrap_url}', timeout=120).read())\\\" "
        "&& chmod 700 /tmp/kitty-bootstrap.sh "
        "&& exec /tmp/kitty-bootstrap.sh"
    )
    return image_name, ("bash", "-lc"), (command,)


'''
    text = text[:start] + helper + text[end:]
    old = '''            (
                temp_template_id,
                temp_image_name,
                temp_docker_entrypoint,
                temp_docker_start_cmd,
            ) = await _create_temporary_template(
                http_client,
                api_key=api_key,
                source_template_id=source_template_id,
                bootstrap_ref=bootstrap_ref,
                run_id=run_id,
            )
'''
    new = '''            (
                temp_image_name,
                temp_docker_entrypoint,
                temp_docker_start_cmd,
            ) = await _direct_deployment_config(
                http_client,
                api_key=api_key,
                source_template_id=source_template_id,
                bootstrap_ref=bootstrap_ref,
            )
'''
    text = replace_once(text, old, new, "batch deployment")
    cleanup = '''            if temp_template_id is not None:
                try:
                    await _template_request(
                        http_client,
                        api_key,
                        "DELETE",
                        f"/templates/{temp_template_id}",
                    )
                except Exception as exc:
                    cleanup_errors.append(f"template {temp_template_id}: {exc}")
'''
    text = replace_once(text, cleanup, "", "batch template cleanup")
    path.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    path = Path("tests/test_runpod_control.py")
    text = path.read_text(encoding="utf-8")
    start = text.index(
        "@pytest.mark.asyncio\n"
        "async def test_create_image_pod_rest_preserves_explicit_startup_overrides():"
    )
    end = text.index(
        "@pytest.mark.asyncio\n"
        "async def test_actual_cost_sums_matching_billing_records():",
        start,
    )
    test = '''@pytest.mark.asyncio
async def test_create_image_pod_rest_preserves_explicit_startup_overrides():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/pods"
        assert request.method == "POST"
        body = json.loads(request.content)
        captured.update(body)
        return httpx.Response(
            201,
            json={
                "id": "rest-pod",
                "name": f"{KITTY_POD_PREFIX}rest",
                "desiredStatus": "RUNNING",
                "adjustedCostPerHr": 0.31,
                "dockerEntrypoint": ["bash", "-lc"],
                "dockerStartCmd": ["exec /tmp/bootstrap.sh"],
                "env": body["env"],
                "gpu": {"displayName": "NVIDIA L4"},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        async with _client(http_client) as client:
            pod = await client.create_image_pod(
                template_id="source-template-only",
                image_name="runpod/comfyui:cuda13.0",
                docker_entrypoint=("bash", "-lc"),
                docker_start_cmd=("exec /tmp/bootstrap.sh",),
                gpu_type_ids=("NVIDIA L4", "NVIDIA RTX A5000"),
                max_hourly_rate=0.60,
                hard_runtime_minutes=55,
                ports=("8000/http",),
                name_suffix="rest",
            )

    assert pod.pod_id == "rest-pod"
    assert captured["templateId"] is None
    assert captured["imageName"] == "runpod/comfyui:cuda13.0"
    assert captured["dockerEntrypoint"] == ["bash", "-lc"]
    assert captured["dockerStartCmd"] == ["exec /tmp/bootstrap.sh"]
    assert captured["gpuTypeIds"] == ["NVIDIA L4", "NVIDIA RTX A5000"]
    assert captured["gpuTypePriority"] == "custom"
    assert captured["ports"] == ["8000/http"]
    assert captured["supportPublicIp"] is False
    assert isinstance(captured["env"], dict)
    assert captured["env"]["KITTY_MANAGED"] == "1"


'''
    path.write_text(text[:start] + test + text[end:], encoding="utf-8")


def main() -> None:
    patch_control()
    patch_batch()
    patch_tests()


if __name__ == "__main__":
    main()
