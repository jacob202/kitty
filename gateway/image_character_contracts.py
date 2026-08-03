"""Executable Image Studio character contracts.

The legacy character tables store names, photos, and gallery rows. They do not
say how those photos condition a model. This module adds an owner-readable JSON
contract beside each character and refuses generation when the selected engine
cannot honor that contract exactly.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

import httpx

from gateway.image_characters import (
    CHARACTER_STORAGE_DIR,
    CharacterError,
    get_character,
    list_character_refs,
)
from gateway.operating_policy import (
    OperatingPolicyError,
    resolve_character_for_engine,
    validate_character_contract,
)

CONTRACT_FILENAME = "character-contract-v1.json"
EXPECTED_IPADAPTER_MODEL = "ip-adapter-plus_sdxl_vit-h.safetensors"


class CharacterContractError(CharacterError):
    """A character exists but lacks a safe executable identity recipe."""


def contract_path(character_id: str) -> Path:
    return CHARACTER_STORAGE_DIR / character_id / CONTRACT_FILENAME


def save_character_contract(
    character_id: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate and atomically persist one character's generation contract."""
    character = get_character(character_id)
    contract = dict(payload)
    supplied_id = contract.get("character_id")
    if supplied_id != character_id:
        raise CharacterContractError(
            f"contract character_id must be {character_id!r}, got {supplied_id!r}"
        )
    contract["name"] = character.name

    try:
        validate_character_contract(contract)
    except OperatingPolicyError as exc:
        raise CharacterContractError(str(exc)) from exc
    _validate_reference_bindings(character_id, contract)

    target = contract_path(character_id)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target.parent.chmod(0o700)
    temporary = target.with_name(f".{target.name}.tmp-{os.getpid()}")
    try:
        temporary.write_text(
            json.dumps(contract, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.chmod(0o600)
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return load_character_contract(character_id)


def load_character_contract(character_id: str) -> dict[str, Any]:
    """Load a character contract and revalidate it against current references."""
    character = get_character(character_id)
    path = contract_path(character_id)
    if not path.is_file():
        raise CharacterContractError(
            f"character {character.name!r} only has legacy metadata/photos; "
            "save a character contract before generating with it"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CharacterContractError(f"character contract is unreadable: {exc}") from exc
    if not isinstance(payload, dict):
        raise CharacterContractError("character contract must be a JSON object")
    if payload.get("character_id") != character_id:
        raise CharacterContractError(
            f"character contract belongs to {payload.get('character_id')!r}, "
            f"not {character_id!r}"
        )
    if payload.get("name") != character.name:
        raise CharacterContractError(
            f"character was renamed to {character.name!r}; resave the contract "
            "so its visible identity metadata is current"
        )
    try:
        validate_character_contract(payload)
    except OperatingPolicyError as exc:
        raise CharacterContractError(str(exc)) from exc
    _validate_reference_bindings(character_id, payload)
    return payload


def delete_character_contract(character_id: str) -> None:
    """Remove only the recipe; character metadata and photographs remain."""
    get_character(character_id)
    contract_path(character_id).unlink(missing_ok=True)


def comfyui_character_capabilities() -> dict[str, Any]:
    """The exact identity behavior implemented by the current ComfyUI workflow."""
    from gateway.image_gen import SDXL_PHOTONIC

    return {
        "engine": "comfyui",
        "base_families": ["sdxl"],
        "identity_methods": ["ipadapter_faceid"],
        "fusion_methods": ["single"],
        "maximum_references": 1,
        "per_reference_weights": False,
        "per_region_weights": False,
        "adapter_models": [EXPECTED_IPADAPTER_MODEL],
        "adapter_strengths": [0.5, 0.7, 0.85],
        "checkpoint": SDXL_PHOTONIC,
        "sampler": "euler",
        "scheduler": "sgm_uniform",
    }


async def comfyui_character_runtime_status() -> tuple[bool, str]:
    """Prove the exact SDXL adapter exists before a character job is created.

    The legacy readiness probe passed when *any* IP-Adapter model existed. Kitty
    was configured with an SD1.5 FaceID file while sending it an SDXL checkpoint,
    so a green readiness light did not mean the workflow was compatible.
    """
    from gateway import image_gen

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{image_gen.COMFY_URL}/object_info")
        if response.status_code != 200:
            return False, f"ComfyUI object_info returned HTTP {response.status_code}"
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return False, f"cannot inspect ComfyUI identity runtime: {exc}"
    if not isinstance(payload, dict):
        return False, "ComfyUI object_info was not a JSON object"

    missing_nodes = sorted(image_gen.COMFY_IDENTITY_NODES.difference(payload))
    if missing_nodes:
        return False, f"ComfyUI identity nodes are missing: {missing_nodes}"
    required = (
        payload.get("IPAdapterModelLoader", {})
        .get("input", {})
        .get("required", {})
    )
    raw_options = required.get("ipadapter_file", [[]])
    options: list[str] = []
    if isinstance(raw_options, list) and raw_options:
        first = raw_options[0]
        if isinstance(first, list):
            options = [str(item) for item in first]
    if EXPECTED_IPADAPTER_MODEL not in options:
        return False, (
            "the SDXL character workflow requires "
            f"{EXPECTED_IPADAPTER_MODEL!r}; available adapter models: {options}"
        )

    # The workflow function reads this module global at call time. Set it only
    # after the exact file is proven present, replacing the legacy SD1.5 default.
    image_gen.IPADAPTER_MODEL = EXPECTED_IPADAPTER_MODEL
    return True, "ready"


def resolve_comfyui_character(character_id: str) -> dict[str, Any]:
    """Resolve the stored contract into arguments the existing workflow honors."""
    contract = load_character_contract(character_id)
    capabilities = comfyui_character_capabilities()
    try:
        resolved = resolve_character_for_engine(contract, capabilities)
    except OperatingPolicyError as exc:
        raise CharacterContractError(str(exc)) from exc

    recipe = resolved["recipe"]
    _require_recipe_value(recipe, "checkpoint", capabilities["checkpoint"])
    _require_recipe_value(recipe, "sampler", capabilities["sampler"])
    _require_recipe_value(recipe, "scheduler", capabilities["scheduler"])
    if recipe.get("denoise") not in {None, 1, 1.0}:
        raise CharacterContractError(
            "the current character workflow is text-to-image and requires denoise 1.0"
        )
    if recipe.get("engine_options"):
        raise CharacterContractError(
            "the current ComfyUI character workflow supports no engine_options; "
            "refusing to ignore them"
        )
    if recipe.get("compatible_loras"):
        raise CharacterContractError(
            "the current ComfyUI character workflow cannot load character LoRAs"
        )

    strength = float(resolved["adapter_strength"])
    supported_strengths = capabilities["adapter_strengths"]
    if strength not in supported_strengths:
        raise CharacterContractError(
            "the current workflow supports identity strengths "
            f"{supported_strengths}, got {strength}; refusing to round the value"
        )
    identity_mode = {
        0.5: "creative",
        0.7: "balanced",
        0.85: "identity_first",
    }[strength]

    reference = resolved["references"][0]
    refs = {item.ref_id: item for item in list_character_refs(character_id)}
    stored = refs[reference["ref_id"]]
    if not Path(stored.storage_path).is_file():
        raise CharacterContractError(
            f"reference file is missing from disk: {stored.storage_path}"
        )

    return {
        **resolved,
        "reference_path": stored.storage_path,
        "identity_mode": identity_mode,
        "width": int(recipe.get("width") or 1024),
        "height": int(recipe.get("height") or 1024),
        "steps": int(recipe.get("steps") or 8),
        "guidance": float(recipe.get("guidance") or 4.5),
    }


def _validate_reference_bindings(
    character_id: str,
    contract: Mapping[str, Any],
) -> None:
    stored_refs = {item.ref_id: item for item in list_character_refs(character_id)}
    contract_refs = contract["identity"]["references"]
    missing = sorted(
        ref["ref_id"] for ref in contract_refs if ref["ref_id"] not in stored_refs
    )
    if missing:
        raise CharacterContractError(
            f"character contract references unknown stored photos: {missing}"
        )
    for ref in contract_refs:
        stored = stored_refs[ref["ref_id"]]
        if ref["purpose"] == "primary_face" and not stored.is_primary:
            raise CharacterContractError(
                f"reference {ref['ref_id']!r} is primary in the contract but not "
                "marked primary in the character library"
            )
        if ref["enabled"] and not Path(stored.storage_path).is_file():
            raise CharacterContractError(
                f"enabled reference file is missing: {stored.storage_path}"
            )


def _require_recipe_value(
    recipe: Mapping[str, Any],
    key: str,
    supported: str,
) -> None:
    configured = recipe.get(key)
    if configured not in {None, supported}:
        raise CharacterContractError(
            f"the current ComfyUI workflow requires {key}={supported!r}, "
            f"got {configured!r}"
        )


__all__ = [
    "CharacterContractError",
    "CONTRACT_FILENAME",
    "EXPECTED_IPADAPTER_MODEL",
    "contract_path",
    "save_character_contract",
    "load_character_contract",
    "delete_character_contract",
    "comfyui_character_capabilities",
    "comfyui_character_runtime_status",
    "resolve_comfyui_character",
]
