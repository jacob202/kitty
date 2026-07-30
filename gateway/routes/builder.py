"""Builder-specific routes — event stream and control surface.

KB-BRAIN-03: exposes the live EventStream with cursor replay and packet
filtering. The cockpit polls /runtime/manifest for structure and subscribes
here for live updates.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from gateway.builder_events import builder_events

router = APIRouter(tags=["builder"])


@router.get("/builder/events")
async def builder_event_stream(
    request: Request,
    session_id: str | None = Query(None),
    cursor: int | None = Query(None),
    packet_id: str | None = Query(None),
):
    """SSE endpoint for live Builder events.

    Query params:
    - ``session_id``: stable client identifier (auto-generated if absent)
    - ``cursor``: replay events from this sequence number onward
    - ``packet_id``: filter to a single packet's events
    """
    client_id = session_id or str(uuid.uuid4())

    async def event_generator():
        async for message in builder_events.subscribe(
            client_id,
            cursor=cursor,
            packet_id=packet_id,
        ):
            if await request.is_disconnected():
                break
            yield message

    return StreamingResponse(event_generator(), media_type="text/event-stream")
