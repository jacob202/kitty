"""Magic Kitty route — cross-project connections for the home dashboard."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query

from gateway import magic_kitty

router = APIRouter(tags=["magic"])


@router.get("/magic")
async def get_magic_insights(force: bool = Query(False)) -> dict:
    """Return cross-project connection insights.

    Caches for 5 minutes. Pass ``?force=true`` to bypass the cache and
    regenerate from live project state.
    """
    return await asyncio.to_thread(magic_kitty.discover_connections, force=force)
