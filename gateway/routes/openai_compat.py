"""Small OpenAI-compatible discovery surface for third-party Kitty clients."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from gateway.model_routing import LITELLM_DEFAULT, USER_FACING_MODELS

router = APIRouter(tags=["openai-compat"])


def _as_openai_model(entry: dict[str, str]) -> dict:
    return {
        "id": entry["id"],
        "object": "model",
        "created": 0,
        "owned_by": "kitty",
        "root": entry["id"],
        "parent": None,
        "permission": [],
        # Open WebUI renders these; without them the menu is a column of slugs.
        "name": entry["name"],
        "description": entry["description"],
    }


# Third-party shells need stable identifiers, not Kitty's transient provider
# inventory. These ids keep routing, memory, policy, and cost selection inside
# Kitty instead of leaking those decisions into each client.
_CATALOGUE: dict[str, dict] = {
    entry["id"]: _as_openai_model(entry) for entry in USER_FACING_MODELS
}
# Retrievable but unlisted: saved chats and older clients still send this id, and
# a 404 on the id they were opened with would strand them.
_CATALOGUE[LITELLM_DEFAULT] = _as_openai_model(
    {
        "id": LITELLM_DEFAULT,
        "name": "Kitty Auto",
        "description": "Everyday use. Kitty reads the message and picks the tier.",
    }
)


@router.get("/v1/models")
def list_models() -> dict:
    """Return the models Kitty offers a human, in menu order."""

    return {
        "object": "list",
        "data": [dict(_CATALOGUE[entry["id"]]) for entry in USER_FACING_MODELS],
    }


@router.get("/v1/models/{model_id}")
def retrieve_model(model_id: str) -> dict:
    """Return one model using the OpenAI retrieval shape."""

    entry = _CATALOGUE.get(model_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Unknown model: {model_id}")
    return dict(entry)
