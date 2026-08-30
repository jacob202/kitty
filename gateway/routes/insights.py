"""Insights endpoints — dream insights + insight lifecycle (issue #270).

The dream-touching endpoints (``/dream/insights``, ``/dream/trigger``,
``/dream/status``) live solely in ``routes/dream.py`` (registered first,
canonical). They were previously duplicated here; the duplicates were
removed so the route surface is single-source and registration order can
no longer pick the handler. This module owns only the insights-specific
and insight-lifecycle paths below.
"""

from __future__ import annotations

from fastapi import APIRouter

from gateway import dream_insights, insight_loop

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


# ── Insight lifecycle (issue #270) ──────────────────────────────────────────


@router.post("/insight-loop/capture")
async def post_capture(
    text: str,
    source_ref: str | None = None,
    category: str | None = None,
    return_at: str | None = None,
    return_policy: str = "next_brief",
    explicit_consent: bool = False,
) -> dict:
    """Capture a new insight. Returns the item id."""
    item_id = insight_loop.capture(
        text=text,
        source_ref=source_ref,
        category=category,
        return_at=return_at,
        return_policy=return_policy,
        explicit_consent=explicit_consent,
    )
    return {"id": item_id}


@router.get("/insight-loop/due")
async def get_due() -> dict:
    """Return approved pending insights that are due for return."""
    return {"insights": insight_loop.list_due()}


@router.get("/insight-loop/insights")
async def list_insights(status: str | None = None, limit: int = 50) -> dict:
    """List insights, optional status filter."""
    return {"insights": insight_loop.list_insights(status=status, limit=limit)}


@router.get("/insight-loop/insight/{item_id}")
async def get_insight(item_id: int) -> dict:
    """Get one insight by id."""
    item = insight_loop.get_insight(item_id)
    if item is None:
        return {"error": "not found"}
    return {"insight": item}


@router.post("/insight-loop/insight/{item_id}/respond")
async def respond_to_insight(
    item_id: int,
    choice: str,
    snooze_until: str | None = None,
    archive_reason: str | None = None,
) -> dict:
    """Respond to a returned insight: act, snooze, or archive."""
    result = insight_loop.respond(
        item_id=item_id,
        choice=choice,
        snooze_until=snooze_until,
        archive_reason=archive_reason,
    )
    return {"insight": result}


@router.get("/insight-loop/metrics")
async def get_metrics() -> dict:
    """Return insight loop metrics."""
    return {"metrics": insight_loop.get_metrics()}
