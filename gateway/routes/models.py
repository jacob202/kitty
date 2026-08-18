"""User-facing model choice views."""

from __future__ import annotations

from fastapi import APIRouter

from gateway.model_presets import build_model_picker

router = APIRouter(tags=["models"])


@router.get("/models/picker")
def get_model_picker() -> dict:
    """Return Kitty's curated model choices without inventing missing evidence."""
    return build_model_picker()
