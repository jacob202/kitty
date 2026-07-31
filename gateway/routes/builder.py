"""Builder-specific routes — event stream and control surface.

KB-BRAIN-03: exposes the live EventStream with cursor replay and packet
filtering. The cockpit polls /runtime/manifest for structure and subscribes
here for live updates.

KB-BRAIN-05: operator command endpoint dispatches typed commands with audit
events and returns structured results.
"""

from __future__ import annotations

import inspect
import logging
import uuid

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from gateway.builder_commands import COMMAND_HANDLERS as _COMMAND_HANDLERS
from gateway.builder_events import builder_events

logger = logging.getLogger("kitty.builder_routes")
router = APIRouter(tags=["builder"])


class OperatorCommandRequest(BaseModel):
    action: str
    task_id: str | None = None
    initiative_id: str | None = None
    packet_id: str | None = None
    reason: str | None = None
    actor: str | None = None
    expected_version: int | None = None


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


@router.post("/builder/command")
async def builder_operator_command(body: OperatorCommandRequest):
    """Dispatch an operator command through canonical Builder APIs.

    Each command is audited: the handler emits a ``command_completed`` event
    into the builder event stream and returns a structured result. The frontend
    must never mutate queue storage or infer success from HTTP 200 alone —
    inspect ``result.ok`` and ``result.error``.
    """
    handler = _COMMAND_HANDLERS.get(body.action)
    if handler is None:
        return {
            "ok": False,
            "error": f"unknown action: {body.action}",
            "available": sorted(_COMMAND_HANDLERS.keys()),
        }

    try:
        supplied = {
            "actor": body.actor or "cockpit-operator",
            "reason": body.reason,
            "task_id": body.task_id,
            "initiative_id": body.initiative_id,
            "expected_version": body.expected_version,
        }
        accepted = inspect.signature(handler).parameters
        kwargs = {
            name: value
            for name, value in supplied.items()
            if name in accepted and value is not None
        }

        result = handler(**kwargs)
        return {
            "ok": result.ok,
            "action": result.action,
            "task_id": result.task_id,
            "error": result.error,
            "detail": result.detail,
            "event_id": result.event_id,
            "evidence": result.evidence,
        }
    except Exception as exc:
        logger.exception("operator command %s failed", body.action)
        return {"ok": False, "action": body.action, "error": str(exc)}
