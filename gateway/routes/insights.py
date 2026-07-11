"""Insights endpoint for Kitty UI — thin FastAPI wrapper.

The dream-touching endpoints (``/dream/insights``, ``/dream/trigger``,
``/dream/status``) live solely in ``routes/dream.py`` (registered first,
canonical). They were previously duplicated here; the duplicates were
removed so the route surface is single-source and registration order can
no longer pick the handler. This module owns only the insights-specific
paths below.
"""

from __future__ import annotations

from fastapi import APIRouter

from gateway import dream_insights

router = APIRouter(tags=["insights"])


@router.get("/insights")
async def get_insights(limit: int = 10) -> dict:
    """Get recent insights from the real dream insight store."""
    return {"insights": dream_insights.load_dream_insights(limit=limit)}


@router.post("/insight/{insight_id}/dismiss")
async def dismiss_insight(insight_id: str) -> dict:
    """Dismiss an insight."""
    dream_insights.dismiss_dream_insight(insight_id)
    return {"dismissed": insight_id}
