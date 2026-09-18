from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
from typing import Any

import pytest

comfy = importlib.import_module("mcp.imagen.engines.comfyui")


class _Response:
    def __init__(
        self,
        payload: Any = None,
        *,
        status_code: int = 200,
        content: bytes = b"",
        text: str = "",
    ) -> None:
        self._payload = payload
        self.status_code = status_code
        self.content = content
        self.text = text

    def json(self) -> Any:
        return self._payload


def _faceid_object_info() -> dict[str, Any]:
    return {
        "CheckpointLoaderSimple": {
            "input": {"required": {"ckpt_name": [[comfy.SD15_CKPT], {}]}}
        },
        "LoraLoader": {
            "input": {
                "required": {
                    "lora_name": [[comfy.BEAR_LORA, comfy.EXPLICIT_LORA], {}]
                }
            }
        },
        "IPAdapterModelLoader": {
            "input": {
                "required": {
                    "ipadapter_file": [[comfy.FACEID_ADAPTER_FILE], {}],
                }
            }
        },
        "IPAdapterInsightFaceLoader": {
            "input": {
                "required": {
                    "provider": [[comfy.FACEID_PROVIDER], {}],
                    "model_name": [[comfy.FACEID_INSIGHTFACE_MODEL], {}],
                }
            }
        },
        "IPAdapterFaceID": {"input": {"required": {}}},
        "LoadImage": {"input": {"required": {}}},
    }


class _FakeClient:
    def __init__(self, *, object_info: dict[str, Any] | None = None) -> None:
        self.object_info = object_info if object_info is not None else _faceid_object_info()
        self.gets: list[tuple[str, dict[str, Any] | None]] = []
        self.posts: list[tuple[str, dict[str, Any]]] = []
        self.prompt_workflow: dict[str, Any] | None = None

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def get(self, url: str, params: dict[str, Any] | None = None) -> _Response:
        self.gets.append((url, params))
        if url.endswith("/object_info"):
            return _Response(self.object_info)
        if "/history/" in url:
            prompt_id = url.rsplit("/", 1)[-1]
            return _Response(
                {
                    prompt_id: {
                        "outputs": {
                            "8": {"images": [{"filename": "out.png"}]},
                        }
                    }
                }
            )
        if url.endswith("/view"):
            return _Response(content=b"generated-image")
        raise AssertionError(f"unexpected GET {url}")

    async def post(self, url: str, **kwargs: Any) -> _Response:
        self.posts.append((url, kwargs))
        if url.endswith("/upload/image"):
            return _Response(
                {
                    "name": kwargs["files"]["image"][0],
                    "subfolder": "kitty_identity",
                    "type": "input",
                }
            )
        if url.endswith("/prompt"):
            self.prompt_workflow = kwargs["json"]["prompt"]
            return _Response({"prompt_id": "prompt-1"})
        raise AssertionError(f"unexpected POST {url}")


@pytest.fixture()
def engine() -> comfy.ComfyuiEngine:
    return comfy.ComfyuiEngine()


def _install_fake_client(monkeypatch: pytest.MonkeyPatch, fake: _FakeClient) -> None:
    monkeypatch.setattr(comfy.httpx, "AsyncClient", lambda **_kwargs: fake)

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(comfy.asyncio, "sleep", _no_sleep)


def test_identity_prompt_forces_sd15_parameters() -> None:
    normal = comfy._parse_comfy("photorealistic portrait")
    locked = comfy._parse_comfy("photorealistic portrait", force_sd15=True)

    assert normal["sdxl"] is True
    assert locked["sdxl"] is False
    assert (locked["w"], locked["h"], locked["cfg"]) == (512, 768, 7.0)


def test_faceid_workflow_routes_sampler_through_conditioned_model() -> None:
    params = comfy._parse_comfy("explicit portrait", force_sd15=True)
    params["seed"] = 123

    workflow = comfy._wf_sd15_faceid(
        "explicit portrait",
        params,
        image_name="kitty_identity/ref.png",
        id_weight=0.9,
        faceidv2_weight=1.3,
    )

    assert workflow["13"]["inputs"]["model"] == ["9", 0]
    assert workflow["13"]["inputs"]["ipadapter"] == ["10", 0]
    assert workflow["13"]["inputs"]["insightface"] == ["11", 0]
    assert workflow["13"]["inputs"]["image"] == ["12", 0]
    assert workflow["13"]["inputs"]["weight"] == 0.9
    assert workflow["13"]["inputs"]["weight_faceidv2"] == 1.3
    assert workflow["6"]["inputs"]["model"] == ["13", 0]
    assert workflow["6"]["inputs"]["seed"] == 123


def test_capability_probe_rejects_missing_node() -> None:
    info = _faceid_object_info()
    del info["IPAdapterFaceID"]

    with pytest.raises(RuntimeError, match="missing required node"):
        comfy._require_faceid_capabilities(info, explicit=False)


def test_capability_probe_rejects_missing_checkpoint() -> None:
    info = _faceid_object_info()
    info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"] = [
        ["other-model.safetensors"],
        {},
    ]

    with pytest.raises(RuntimeError, match="does not offer configured value"):
        comfy._require_faceid_capabilities(info, explicit=False)


def test_explicit_capability_probe_requires_explicit_lora() -> None:
    info = _faceid_object_info()
    info["LoraLoader"]["input"]["required"]["lora_name"] = [
        [comfy.BEAR_LORA],
        {},
    ]

    with pytest.raises(RuntimeError, match="does not offer configured value"):
        comfy._require_faceid_capabilities(info, explicit=True)


def test_capability_probe_rejects_wrong_adapter() -> None:
    info = _faceid_object_info()
    info["IPAdapterModelLoader"]["input"]["required"]["ipadapter_file"] = [
        ["some-other-adapter.bin"],
        {},
    ]

    with pytest.raises(RuntimeError, match="does not offer configured value"):
        comfy._require_faceid_capabilities(info, explicit=False)


def test_identity_reference_requires_exactly_one_existing_file(tmp_path: Path) -> None:
    ref = tmp_path / "ref.png"
    ref.write_bytes(b"reference")

    assert comfy._identity_reference([ref]) == ref
    with pytest.raises(ValueError, match="exactly one"):
        comfy._identity_reference([])
    with pytest.raises(ValueError, match="exactly one"):
        comfy._identity_reference([ref, ref])
    with pytest.raises(FileNotFoundError):
        comfy._identity_reference([tmp_path / "missing.png"])


def test_identity_generation_uploads_reference_and_uses_faceid(
    engine: comfy.ComfyuiEngine,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ref = tmp_path / "ref.png"
    ref.write_bytes(b"identity-bytes")
    fake = _FakeClient()
    _install_fake_client(monkeypatch, fake)

    result = asyncio.run(
        engine.generate_async(
            "photorealistic portrait",
            seed=77,
            identity_images=[ref],
            id_weight=0.8,
            faceidv2_weight=1.2,
        )
    )

    assert result == b"generated-image"
    assert [url.rsplit("/", 1)[-1] for url, _ in fake.posts] == ["image", "prompt"]
    assert fake.prompt_workflow is not None
    assert fake.prompt_workflow["12"]["inputs"]["image"].startswith("kitty_identity/")
    assert fake.prompt_workflow["13"]["inputs"]["weight"] == 0.8
    assert fake.prompt_workflow["13"]["inputs"]["weight_faceidv2"] == 1.2
    assert fake.prompt_workflow["6"]["inputs"]["seed"] == 77
    assert fake.prompt_workflow["6"]["inputs"]["model"] == ["13", 0]
    assert fake.prompt_workflow["1"]["inputs"]["ckpt_name"] == comfy.SD15_CKPT


def test_missing_faceid_capability_fails_before_upload_or_generation(
    engine: comfy.ComfyuiEngine,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ref = tmp_path / "ref.png"
    ref.write_bytes(b"identity-bytes")
    fake = _FakeClient(object_info={"LoadImage": {"input": {"required": {}}}})
    _install_fake_client(monkeypatch, fake)

    with pytest.raises(RuntimeError, match="missing required node"):
        asyncio.run(engine.generate_async("portrait", identity_images=[ref]))

    assert fake.posts == []


def test_unconditioned_generation_does_not_probe_or_upload(
    engine: comfy.ComfyuiEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeClient()
    _install_fake_client(monkeypatch, fake)

    result = asyncio.run(engine.generate_async("portrait", seed=91))

    assert result == b"generated-image"
    assert all(not url.endswith("/object_info") for url, _ in fake.gets)
    assert [url.rsplit("/", 1)[-1] for url, _ in fake.posts] == ["prompt"]
    assert fake.prompt_workflow is not None
    assert "13" not in fake.prompt_workflow
    assert fake.prompt_workflow["6"]["inputs"]["seed"] == 91


def test_zero_identity_images_rejects_before_client_creation(
    engine: comfy.ComfyuiEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _unexpected_client(**_kwargs: Any) -> None:
        raise AssertionError("client should not be created")

    monkeypatch.setattr(comfy.httpx, "AsyncClient", _unexpected_client)

    with pytest.raises(ValueError, match="exactly one"):
        asyncio.run(engine.generate_async("portrait", identity_images=[]))


def test_invalid_identity_weight_rejects_before_client_creation(
    engine: comfy.ComfyuiEngine,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ref = tmp_path / "ref.png"
    ref.write_bytes(b"identity")

    def _unexpected_client(**_kwargs: Any) -> None:
        raise AssertionError("client should not be created")

    monkeypatch.setattr(comfy.httpx, "AsyncClient", _unexpected_client)

    with pytest.raises(ValueError, match="id_weight"):
        asyncio.run(
            engine.generate_async(
                "portrait",
                identity_images=[ref],
                id_weight=3.1,
            )
        )


@pytest.mark.parametrize("value", [True, "high", 0, -0.1, 3.1])
def test_identity_weight_validation(value: object) -> None:
    with pytest.raises(ValueError):
        comfy._identity_weight(value, label="id_weight", default=0.9, max_value=3.0)
