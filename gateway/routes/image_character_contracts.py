"""Image character contracts and the generation path they actually control."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from gateway.image_character_contracts import (
    CharacterContractError,
    delete_character_contract,
    load_character_contract,
    resolve_comfyui_character,
    save_character_contract,
)
from gateway.image_characters import CharacterNotFoundError

router = APIRouter(prefix="/image/characters", tags=["image-characters"])


class CharacterContractBody(BaseModel):
    contract: dict[str, Any]


class CharacterGenerateBody(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    negative_prompt: str | None = Field(default=None, max_length=8000)
    guidance_tags: list[str] = Field(default_factory=list, max_length=20)


@router.get("/{character_id}/contract")
def character_contract_get(character_id: str) -> dict[str, Any]:
    try:
        return {"contract": load_character_contract(character_id)}
    except CharacterNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CharacterContractError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/{character_id}/contract")
def character_contract_put(
    character_id: str,
    body: CharacterContractBody,
) -> dict[str, Any]:
    try:
        contract = save_character_contract(character_id, body.contract)
        return {"contract": contract, "ready": True}
    except CharacterNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CharacterContractError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/{character_id}/contract")
def character_contract_delete(character_id: str) -> dict[str, Any]:
    try:
        delete_character_contract(character_id)
        return {"deleted": True, "character_id": character_id}
    except CharacterNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{character_id}/resolved")
def character_contract_resolved(character_id: str) -> dict[str, Any]:
    """Show exactly what the current ComfyUI workflow will consume."""
    try:
        return {"resolved": resolve_comfyui_character(character_id)}
    except CharacterNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CharacterContractError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{character_id}/generate")
async def character_generate(
    character_id: str,
    body: CharacterGenerateBody,
) -> dict[str, Any]:
    """Generate only after the character contract resolves without omissions."""
    from gateway.image_runner import ImageRunnerError, run

    try:
        # Resolve before creating a job so unsupported settings never spend or
        # leave a failed job behind merely because a UI control did nothing.
        resolved = resolve_comfyui_character(character_id)
        result = await run(
            "comfyui",
            body.prompt,
            character_id=character_id,
            negative_prompt=body.negative_prompt,
            guidance_tags=body.guidance_tags,
        )
        return {
            "job_id": result.job_id,
            "prompt_id": result.prompt_id,
            "filename": result.filename,
            "engine": result.engine,
            "character_id": character_id,
            "recipe_id": resolved["recipe_id"],
            "identity_method": resolved["identity_method"],
            "reference_ids": [ref["ref_id"] for ref in resolved["references"]],
            "character_weight": result.character_weight,
        }
    except CharacterNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CharacterContractError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ImageRunnerError as exc:
        status = 503 if "not running" in str(exc).lower() else 422
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc


__all__ = ["router"]
