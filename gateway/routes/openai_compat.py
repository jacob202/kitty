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
        "name": entry["name"],
        "description": entry["description"],
    }


_CATALOGUE: dict[str, dict] = {
    entry["id"]: _as_openai_model(entry) for entry in USER_FACING_MODELS
}
_CATALOGUE[LITELLM_DEFAULT] = _as_openai_model(
    {
        "id": LITELLM_DEFAULT,
        "name": "Kitty Auto",
        "description": "Everyday use. Kitty reads the message and picks the tier.",
    }
)


def _selected_provider() -> str | None:
    """Read the preference without invoking a provider or requiring its key."""
    from gateway.provider_prefs import active_provider

    return active_provider()


def _visible_catalogue() -> list[dict]:
    """Return only menu choices the current execution path can honor.

    LiteLLM/automatic routing owns Kitty's virtual model aliases. OpenRouter's
    direct fallback also maps them explicitly. Other exact-provider paths select
    one provider-specific default model and cannot guarantee that choosing
    Think, Code, or Vision will reach the advertised upstream model. Showing
    those rows would make the menu lie, so exact-provider mode collapses to one
    honest row until that provider gains explicit alias mappings.
    """
    selected = _selected_provider()
    if selected is None or selected == "openrouter":
        return [dict(_CATALOGUE[entry["id"]]) for entry in USER_FACING_MODELS]

    auto = dict(_CATALOGUE["kitty-auto"])
    label = selected.replace("_", " ").title()
    auto["name"] = f"Kitty — {label}"
    auto["description"] = (
        f"Uses the model configured for the selected {label} provider. "
        "Model-specific choices are hidden because this provider cannot "
        "guarantee their advertised models."
    )
    return [auto]


@router.get("/v1/models")
def list_models() -> dict:
    """Return the truthful human-facing model menu in display order."""
    return {"object": "list", "data": _visible_catalogue()}


@router.get("/v1/models/{model_id}")
def retrieve_model(model_id: str) -> dict:
    """Retrieve saved/legacy model ids even when they are hidden from the menu."""
    entry = _CATALOGUE.get(model_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Unknown model: {model_id}")
    return dict(entry)
