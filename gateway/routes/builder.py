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
from gateway.models.builder import BuilderCommandRequest

logger = logging.getLogger("kitty.builder_routes")
router = APIRouter(tags=["builder"])


# Kept as a module-level alias for callers importing the old route model.
OperatorCommandRequest = BuilderCommandRequest
# Kept for callers/tests that inspected the route's old registry alias.
_COMMAND_HANDLERS = COMMAND_HANDLERS


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


@router.get("/builder/supervisor")
async def builder_supervisor_status():
    """Read-only projection of the autonomous supervisor's own state.

    Distinguishes work a tick would start right now (``eligible_now``, owning
    initiative active) from work that is dispatchable in every respect except
    that its initiative is paused (``on_hold``), which no tick will ever pick
    up. Both counts come from ``dispatchable_counts()``, which shares one
    predicate with the launching path — a projection that counted eligibility
    differently would promise the operator a number the tick does not honour.
    This route never queries queue storage itself.
    """
    from gateway import builder_supervisor as bs

    try:
        summary = bs.control_plane_summary()
    except Exception as exc:
        logger.exception("builder supervisor status read failed")
        raise HTTPException(
            status_code=503, detail=f"supervisor status read failed: {exc}"
        ) from exc

    return {
        "schema_version": 1,
        "running": len(summary["active_runs"]) > 0,
        "active_runs": summary["active_runs"],
        "eligible_now": summary["eligible_now"],
        "on_hold": summary["on_hold"],
        # The supervisor does not record when it last ticked anywhere durable
        # (no receipt log, no launchd bookkeeping); reporting anything but
        # null here would be fabricated.
        "last_tick_at": None,
        "lock_path": summary["lock_path"],
        "budget": summary["budget"],
    }


@router.post("/builder/supervisor/tick")
async def builder_supervisor_tick():
    """Run exactly one supervisor tick and return a structured result.

    Mirrors ``/builder/command``: never lets an exception escape as a 500,
    and the caller must inspect ``ok`` rather than infer success from HTTP
    200 alone. A concurrent tick is not an error — it is reported as
    ``ok: true`` with an empty ``started`` list and the ``locked`` detail.
    """
    from gateway import builder_supervisor as bs

    try:
        receipt = bs.tick()
    except Exception as exc:
        logger.exception("builder supervisor tick failed")
        return {"ok": False, "started": [], "error": str(exc), "detail": None}

    if receipt["status"] not in {"ok", "locked"}:
        errors = [entry["error"] for entry in receipt["launched"] if "error" in entry]
        return {
            "ok": False,
            "started": receipt["launched"],
            "error": "; ".join(errors) or "supervisor tick reported an error",
            "detail": receipt,
        }

    return {
        "ok": True,
        "started": receipt["launched"],
        "error": None,
        "detail": receipt,
    }
