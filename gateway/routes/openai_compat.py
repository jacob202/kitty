"""Small OpenAI-compatible discovery surface for third-party Kitty clients."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["openai-compat"])

# Third-party shells need a stable model identifier, not Kitty's transient
# provider inventory. ``kitty-default`` keeps routing, memory, policy, and cost
# selection inside Kitty instead of leaking those decisions into each client.
_KITTY_MODEL = {
    "id": "kitty-default",
    "object": "model",
    "created": 0,
    "owned_by": "kitty",
    "root": "kitty-default",
    "parent": None,
    "permission": [],
}


@router.get("/v1/models")
def list_models() -> dict:
    """Return the stable virtual model understood by Kitty's chat endpoint."""

    return {"object": "list", "data": [dict(_KITTY_MODEL)]}


@router.get("/v1/models/{model_id}")
def retrieve_model(model_id: str) -> dict:
    """Return one model using the OpenAI retrieval shape."""

    if model_id != _KITTY_MODEL["id"]:
        raise HTTPException(status_code=404, detail=f"Unknown model: {model_id}")
    return dict(_KITTY_MODEL)
