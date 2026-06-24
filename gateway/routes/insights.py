"""Insights endpoint for Kitty UI — thin FastAPI wrapper.

The dream-touching endpoints (``/dream/insights``, ``/dream/trigger``,
``/dream/status``) duplicate paths registered by ``routes/dream.py``.
FastAPI keeps the first-registered handler, so the dream routes win.
The wrappers below still exist (spec G2: no endpoint is renamed,
deleted, or merged); they are functionally dead while the dream
routes are registered first, and become live again automatically if
registration order changes.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from gateway import dream_insights, insights

from gateway.memory_consolidation import get_last_run_info
from gateway.routes.dream import dismiss_dream_insight, load_dream_insights

router = APIRouter(tags=["insights"])


@router.get("/insights")
async def get_insights(limit: int = 10) -> dict:
    """Get recent user insights from the real dream insight store."""
    return {"insights": insights.list_insights(limit=limit)}


@router.get("/dream/insights")
async def get_dream_insights(limit: int = 10) -> dict:
    """Alias for /insights for backward compatibility."""
    return {"insights": insights.list_insights(limit=limit)}


@router.post("/insight/{insight_id}/dismiss")
async def dismiss_insight(insight_id: str) -> dict:
    """Dismiss an insight."""
    insights.dismiss_insight(insight_id)
    return {"dismissed": insight_id}


@router.post("/dream/trigger")
async def trigger_dream() -> dict:
    """Trigger a dream/consolidation cycle.

    Delegates to ``dream_insights.trigger_dream`` (the real one).
    The dream route in ``routes/dream.py`` registers first and
    shadows this endpoint, so it is effectively dead at runtime.
    """
    dream_insights.trigger_dream()
    return {"status": "consolidation triggered"}


@router.get("/dream/status")
async def dream_status() -> dict:
    """Get dream/consolidation status.

    Delegates to ``dream_insights.dream_status`` (the real one).
    The dream route in ``routes/dream.py`` registers first and
    shadows this endpoint, so it is effectively dead at runtime.
    """
    return dream_insights.dream_status()
