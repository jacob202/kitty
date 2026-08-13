"""Version endpoint — returns the current Kitty version."""

from __future__ import annotations

import os

from fastapi import APIRouter

VERSION = "0.1.0"
router = APIRouter(tags=["version"])


@router.get("/version")
async def get_version():
    """Return the current Kitty version string."""
    version = os.environ.get("KITTY_VERSION", "").strip() or VERSION
    return {"version": version}
