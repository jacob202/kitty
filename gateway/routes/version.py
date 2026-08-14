"""Version endpoint — returns the current Kitty version."""

from __future__ import annotations

from fastapi import APIRouter

VERSION = "0.1.0"
router = APIRouter(tags=["version"])


@router.get("/version")
async def get_version():
    """Return the current Kitty version string."""
    return {"version": VERSION}
