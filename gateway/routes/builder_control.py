"""Builder control deck — run/pause/resume/cancel from the UI.

Every action goes through the action queue at T0 (auto-execute, logged).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from gateway.builder_commands import command_result_payload, dispatch_operator_command
from gateway.models.builder import BuilderCommandRequest

logger = logging.getLogger("kitty.builder_control")
router = APIRouter(tags=["builder"])


# Compatibility alias for clients that imported the legacy request name.
BuilderActionRequest = BuilderCommandRequest

_CANONICAL_ACTIONS = frozenset({"requeue", "recover_stale"})

_LEGACY_ACTION_KINDS = {
    "run_next": "builder.run_next",
    "pause": "builder.pause_initiative",
    "resume": "builder.resume_initiative",
    "cancel": "builder.cancel_task",
    "cleanup": "builder.cleanup",
}


@router.post("/builder/action")
def builder_action(body: BuilderActionRequest):
    if body.action in _CANONICAL_ACTIONS:
        result = dispatch_operator_command(
            body.model_copy(update={"actor": body.actor or "builder-ui"})
        )
        return command_result_payload(result)

    from gateway.action_queue import execute, propose

    kind = _LEGACY_ACTION_KINDS.get(body.action)
    if kind is None:
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
        executed = execute(action["id"])
        if executed["status"] == "failed":
            return {"ok": False, "action_id": action["id"], "error": executed["result"]}
        return {"ok": True, "action_id": action["id"]}
    except Exception as exc:
        logger.warning("Builder action %s failed: %s", body.action, exc)
        return {"ok": False, "error": str(exc)}
