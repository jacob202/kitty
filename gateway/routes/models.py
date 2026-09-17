"""User-facing model choice views."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from gateway.http_client import get_http_client
from gateway.model_presets import build_model_picker
from gateway.paths import LITELLM_BASE, LITELLM_KEY

logger = logging.getLogger("kitty.gateway")
router = APIRouter(tags=["models"])


@router.get("/models/picker")
def get_model_picker() -> dict:
    """Return Kitty's curated model choices without inventing missing evidence."""
    return build_model_picker()


@router.get("/api/models")
async def api_models():
    """Return available models with display names resolved from the routing config."""
    from gateway.model_routing import describe_routing

    routing = describe_routing()
    alias_map = {r["alias"]: r["upstream_model"] for r in routing.get("routes", []) if r.get("alias")}

    client = await get_http_client()
    try:
        resp = await client.get(
            f"{LITELLM_BASE}/v1/models",
            headers={"Authorization": f"Bearer {LITELLM_KEY}"},
        )
        if resp.status_code != 200:
            detail = getattr(resp, "text", "")[:500]
            raise HTTPException(
                status_code=502,
                detail=(
                    f"LiteLLM model discovery returned HTTP {resp.status_code}"
                    + (f": {detail}" if detail else "")
                ),
            )

        data = resp.json()
        models = data.get("data", [])
        for model in models:
            alias = model.get("id", "")
            upstream = alias_map.get(alias, "")
            if upstream:
                model["display_name"] = upstream.split("/")[-1]

        return data

    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Failed to fetch models from LiteLLM: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"LiteLLM model discovery failed: {exc}",
        ) from exc


@router.get("/api/model-routing")
async def api_model_routing():
    """Which provider each kitty-* alias actually calls, and whether its key is set.

    /api/models only returns alias ids, which is why an out-of-credit provider
    was indistinguishable from a healthy one everywhere in the UI.
    """
    from gateway.model_routing import describe_routing

    return describe_routing()
