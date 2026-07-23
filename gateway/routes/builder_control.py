"""Builder control deck — run/pause/resume/cancel from the UI.

Every action goes through the action queue at T0 (auto-execute, logged).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger("kitty.builder_control")
router = APIRouter(tags=["builder"])


class BuilderActionRequest(BaseModel):
    action: str
    initiative_id: str | None = None
    packet_id: str | None = None
    reason: str | None = None


@router.post("/builder/action")
def builder_action(body: BuilderActionRequest):
    from gateway.action_queue import propose, execute

    action_map = {
        "run_next": "builder.run_next",
        "pause": "builder.pause_initiative",
        "resume": "builder.resume_initiative",
        "cancel": "builder.cancel_task",
        "cleanup": "builder.cleanup",
    }

    kind = action_map.get(body.action)
    if not kind:
        return {"ok": False, "error": f"Unknown action: {body.action}"}

    try:
        payload = {}
        if body.initiative_id:
            payload["initiative_id"] = body.initiative_id
        if body.packet_id:
            payload["packet_id"] = body.packet_id
        if body.reason:
            payload["reason"] = body.reason

        action = propose(
            source_kind="builder-ui",
            kind=kind,
            title=f"Builder: {body.action} on {body.packet_id or body.initiative_id or 'queue'}",
            preview=f"User requested {body.action} from the Builder surface",
            payload=payload,
        )
        execute(action["id"])
        return {"ok": True, "action_id": action["id"]}
    except Exception as exc:
        logger.warning("Builder action %s failed: %s", body.action, exc)
        return {"ok": False, "error": str(exc)}
