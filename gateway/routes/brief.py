"""Morning brief routes."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter

logger = logging.getLogger("kitty.gateway")
router = APIRouter(tags=["brief"])


@router.get("/brief")
@router.get("/api/brief")
async def morning_brief():
    from gateway.brief import generate_brief, generate_fast_brief, get_cached_brief

    cached = get_cached_brief()
    if cached:
        return cached

    try:
        return await asyncio.wait_for(asyncio.to_thread(generate_brief), timeout=1.0)
    except asyncio.TimeoutError:
        logger.warning("Morning brief timed out; returning fast fallback brief.")
        stale = get_cached_brief(max_age_seconds=None)
        if stale:
            return stale
        return generate_fast_brief()
