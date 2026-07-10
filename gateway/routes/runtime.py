"""Authoritative runtime capability manifest."""

from __future__ import annotations

from fastapi import APIRouter

from gateway.runtime_manifest import compose_manifest

router = APIRouter(tags=["runtime"])


@router.get("/runtime/manifest")
async def get_runtime_manifest(project_id: int | None = None) -> dict:
    """Return a revisioned snapshot of Kitty's observed runtime truth."""
    return await compose_manifest(project_id=project_id)
