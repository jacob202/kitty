from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from gateway.app import app
from gateway.image_character_contracts import (
    EXPECTED_IPADAPTER_MODEL,
    CharacterContractError,
    comfyui_character_runtime_status,
    contract_path,
    load_character_contract,
    resolve_comfyui_character,
    save_character_contract,
)


@dataclass
class _Character:
    character_id: str = "char_jacob"
    name: str = "Jacob"


@dataclass
class _Ref:
    ref_id: str
    storage_path: str
    is_primary: bool = True


def _contract() -> dict:
    from gateway.image_gen import SDXL_PHOTONIC

    return {
        "schema_version": 1,
        "character_id": "char_jacob",
        "name": "Jacob",
        "description": {
            "appearance": "late-thirties man with short salt-and-pepper hair",
            "preserve": ["natural asymmetry", "apparent age"],
            "exclude": ["beautification", "waxy skin"],
        },
        "identity": {
            "method": "ipadapter_faceid",
            "base_family": "sdxl",
            "adapter_model": EXPECTED_IPADAPTER_MODEL,
            "adapter_strength": 0.7,
            "fusion_method": "single",
            "allow_generated_derivatives": False,
            "references": [
                {
                    "ref_id": "ref_primary",
                    "purpose": "primary_face",
                    "provenance": "real_photo",
                    "enabled": True,
                    "weight": 1.0,
                    "face_weight": 1.0,
                    "body_weight": 1.0,
                    "quality_score": 0.9,
                    "notes": "front-facing natural-light photograph",
                }
            ],
        },
        "prompt": {
            "positive": "natural skin texture, documentary photograph",
            "negative": "rejuvenated, symmetrical face",
        },
        "recipe": {
            "recipe_id": "jacob-sdxl-ipadapter-v1",
            "engine": "comfyui",
            "sampler": "euler",
            "scheduler": "sgm_uniform",
            "steps": 20,
            "guidance": 4.5,
            "denoise": 1.0,
            "width": 896,
            "height": 1152,
            "checkpoint": SDXL_PHOTONIC,
            "compatible_loras": [],
            "incompatible_loras": [],
            "engine_options": {},
        },
    }


@pytest.fixture
def character_store(tmp_path, monkeypatch):
    reference = tmp_path / "ref.png"
    reference.write_bytes(b"png")
    ref = _Ref("ref_primary", str(reference))
    monkeypatch.setattr(
        "gateway.image_character_contracts.CHARACTER_STORAGE_DIR",
        tmp_path / "characters",
    )
    monkeypatch.setattr(
        "gateway.image_character_contracts.get_character",
        lambda character_id: _Character(character_id=character_id),
    )
    monkeypatch.setattr(
        "gateway.image_character_contracts.list_character_refs",
        lambda character_id: [ref],
    )
    return tmp_path, ref


def test_contract_is_atomic_owner_readable_state(character_store):
    save_character_contract("char_jacob", _contract())
    path = contract_path("char_jacob")

    assert load_character_contract("char_jacob")["identity"]["references"][0][
        "ref_id"
    ] == "ref_primary"
    assert path.is_file()
    assert path.stat().st_mode & 0o777 == 0o600
    assert not list(path.parent.glob(".*.tmp-*"))


def test_legacy_character_without_contract_fails_loudly(character_store):
    with pytest.raises(CharacterContractError, match="legacy metadata/photos"):
        load_character_contract("char_jacob")


def test_contract_cannot_name_an_unstored_photo(character_store):
    contract = _contract()
    contract["identity"]["references"][0]["ref_id"] = "not_stored"

    with pytest.raises(CharacterContractError, match="unknown stored photos"):
        save_character_contract("char_jacob", contract)


def test_current_engine_refuses_to_round_identity_strength(character_store):
    contract = _contract()
    contract["identity"]["adapter_strength"] = 0.73
    save_character_contract("char_jacob", contract)

    with pytest.raises(CharacterContractError, match="refusing to round"):
        resolve_comfyui_character("char_jacob")


def test_current_engine_resolves_every_consumed_setting(character_store):
    save_character_contract("char_jacob", _contract())

    resolved = resolve_comfyui_character("char_jacob")

    assert resolved["identity_mode"] == "balanced"
    assert resolved["reference_path"].endswith("ref.png")
    assert resolved["width"] == 896
    assert resolved["height"] == 1152
    assert resolved["steps"] == 20
    assert resolved["guidance"] == 4.5
    assert "salt-and-pepper" in resolved["positive_prompt"]


class _ObjectInfoResponse:
    status_code = 200

    def __init__(self, models: list[str]):
        self._models = models

    def json(self):
        return {
            "IPAdapter": {},
            "IPAdapterModelLoader": {
                "input": {
                    "required": {
                        "ipadapter_file": [self._models],
                    }
                }
            },
        }


class _AsyncClient:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url):
        return self.response


@pytest.mark.asyncio
async def test_runtime_rejects_the_legacy_sd15_adapter(monkeypatch):
    response = _ObjectInfoResponse(["ip-adapter-faceid_sd15.bin"])
    monkeypatch.setattr(
        "gateway.image_character_contracts.httpx.AsyncClient",
        lambda timeout: _AsyncClient(response),
    )

    ready, reason = await comfyui_character_runtime_status()

    assert ready is False
    assert EXPECTED_IPADAPTER_MODEL in reason
    assert "sd15" in reason


@pytest.mark.asyncio
async def test_runtime_selects_the_exact_sdxl_adapter(monkeypatch):
    from gateway import image_gen

    response = _ObjectInfoResponse([EXPECTED_IPADAPTER_MODEL])
    monkeypatch.setattr(
        "gateway.image_character_contracts.httpx.AsyncClient",
        lambda timeout: _AsyncClient(response),
    )
    monkeypatch.setattr(image_gen, "IPADAPTER_MODEL", "legacy.bin")

    ready, reason = await comfyui_character_runtime_status()

    assert (ready, reason) == (True, "ready")
    assert image_gen.IPADAPTER_MODEL == EXPECTED_IPADAPTER_MODEL


def test_contract_api_returns_conflict_when_character_is_not_generation_ready():
    client = TestClient(app)
    with patch(
        "gateway.routes.image_character_contracts.load_character_contract",
        side_effect=CharacterContractError("legacy metadata/photos only"),
    ):
        response = client.get("/image/characters/char_x/contract")

    assert response.status_code == 409
    assert "legacy metadata/photos" in response.json()["detail"]


def test_generation_endpoint_resolves_before_spending():
    client = TestClient(app)
    with (
        patch(
            "gateway.routes.image_character_contracts.resolve_comfyui_character",
            side_effect=CharacterContractError("unsupported fusion method"),
        ),
        patch(
            "gateway.image_runner.run",
            new_callable=AsyncMock,
        ) as run,
    ):
        response = client.post(
            "/image/characters/char_x/generate",
            json={"prompt": "at a lake"},
        )

    assert response.status_code == 409
    run.assert_not_awaited()
