"""Magic Kitty route — cross-project connections for the home dashboard."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query

from gateway import magic_kitty

from pydantic import BaseModel, Field
from typing import Any


class MagicInsightItem(BaseModel):
    label: str
    value: str


class MagicInsightsResponse(BaseModel):
    insights: list[MagicInsightItem]


router = APIRouter(tags=["magic"])


@router.get("/magic", response_model=MagicInsightsResponse)
async def get_magic_insights(force: bool = Query(False)) -> dict:
    """Return cross-project connection insights.

    Caches for 5 minutes. Pass ``?force=true`` to bypass the cache and
    regenerate from live project state.
    """
    return await asyncio.to_thread(magic_kitty.discover_connections, force=force)
