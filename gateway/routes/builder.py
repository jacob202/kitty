"""Builder-specific routes — event stream and control surface.

KB-BRAIN-03: exposes the live EventStream with cursor replay and packet
filtering. The cockpit polls /runtime/manifest for structure and subscribes
here for live updates.

KB-BRAIN-05: operator command endpoint dispatches typed commands with audit
events and returns structured results.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from gateway.builder_commands import (
    COMMAND_HANDLERS,
    command_result_payload,
    dispatch_operator_command,
)
from gateway.builder_events import builder_events
from gateway.builder_initiative import (
    BaseSHAResolutionError,
    InitiativeConflictError,
    ManifestError,
    MissionSubmissionError,
    submit_mission,
)
from gateway.models.builder import BuilderCommandRequest, Mission
from gateway.paths import BUILDER_QUEUE_DB, PROJECT_ROOT

logger = logging.getLogger("kitty.builder_routes")
router = APIRouter(tags=["builder"])


# Kept as a module-level alias for callers importing the old route model.
OperatorCommandRequest = BuilderCommandRequest
# Kept for callers/tests that inspected the route's old registry alias.
_COMMAND_HANDLERS = COMMAND_HANDLERS


@router.post("/builder/initiative")
def submit_builder_mission(body: Mission):
    """Accept Kitty's approved Mission and materialize Builder work durably."""
    try:
        return submit_mission(
            body,
            db_path=BUILDER_QUEUE_DB,
            repo_root=PROJECT_ROOT,
        )
    except (MissionSubmissionError, ManifestError, BaseSHAResolutionError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InitiativeConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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
    try:
        result = dispatch_operator_command(body)
        return command_result_payload(result)
    except Exception as exc:
        logger.exception("operator command %s failed", body.action)
        return {"ok": False, "action": body.action, "error": str(exc)}
