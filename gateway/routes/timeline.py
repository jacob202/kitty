"""Unified activity timeline endpoint — a read-only projection over evidence."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from gateway import activity_timeline

router = APIRouter(tags=["timeline"])

TimelineFilter = Literal["all", "automations", "images", "memory", "system", "failures"]


@router.get("/activity/timeline")
def activity_timeline_view(
    filter: TimelineFilter = "all",
    limit: int = Query(50, ge=1, le=200),
):
    """Return a chronological projection of meaningful Kitty activity."""
    return {
        "entries": activity_timeline.build_timeline(filter=filter, limit=limit),
    }
