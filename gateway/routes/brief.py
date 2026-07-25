"""Morning brief routes."""


from __future__ import annotations
from pydantic import BaseModel

import asyncio
import logging

from fastapi import APIRouter

logger = logging.getLogger("kitty.gateway")
class BriefBriefResponse(BaseModel):
    model_config = {"extra": "allow"}


class BriefApiBriefResponse(BaseModel):
    model_config = {"extra": "allow"}



router = APIRouter(tags=["brief"])


@router.get("/brief", response_model=BriefBriefResponse)
@router.get("/api/brief", response_model=BriefApiBriefResponse)
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
        # The fallback still reads local stores and memory. Running it inline
        # here blocks the event loop exactly when the gateway is already under
        # pressure, making unrelated health and chat requests look offline.
        return await asyncio.to_thread(generate_fast_brief)
