"""macOS Calendar integration routes."""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["calendar"])


async def _calendar_events_response(fetch_events):
    """Run blocking Calendar AppleScript off the event loop."""
    from gateway.calendar_integration import is_available

    if not is_available():
        return {"available": False, "events": []}
    events = await asyncio.to_thread(fetch_events)
    return {"available": True, "events": events}


@router.get("/calendar/today")
async def calendar_today():
    from gateway.calendar_integration import get_today

    return await _calendar_events_response(get_today)


@router.get("/calendar/upcoming")
async def calendar_upcoming(days: int = 7):
    from gateway.calendar_integration import get_upcoming

    return await _calendar_events_response(lambda: get_upcoming(days))


class CalendarCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    notes: str = ""


@router.post("/calendar/create")
async def calendar_create(payload: CalendarCreateRequest):
    from gateway.calendar_integration import create, is_available

    if not is_available():
        raise HTTPException(
            status_code=400, detail="Calendar not available (macOS only)"
        )
    success = await asyncio.to_thread(
        create,
        payload.title,
        payload.start_time,
        payload.end_time,
        payload.notes,
    )
    return {"created": success}
