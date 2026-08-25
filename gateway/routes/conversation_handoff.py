"""HTTP surface for the conversation -> approved KittyBuilder job handoff.

Mirrors the KittyBuilder MCP bridge's propose/approve/resume contract
(``mcp/builder``) so Kitty's native chat UI and any MCP client share one
approval mechanism and one durable authority. See
``gateway/conversation_handoff.py`` for the delegation this wraps.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from gateway import conversation_handoff

logger = logging.getLogger("kitty.conversation_handoff_routes")
router = APIRouter(tags=["conversation-handoff"])


class ProposeRequest(BaseModel):
    objective: str = Field(min_length=1, max_length=2000)
    instructions: str = Field(min_length=1, max_length=8000)
    allowed_paths: list[str] = Field(min_length=1)
    initiative_id: str | None = None
    title: str | None = None
    acceptance_criteria: list[str] | None = None
    validation_commands: list[str] | None = None


class ApproveRequest(BaseModel):
    prepared_manifest: dict
    expected_manifest_sha: str
    expected_base_sha: str
    approval_nonce: str
    confirmed: bool = False


@router.post("/builder/conversation/propose")
def propose_builder_job(body: ProposeRequest) -> dict:
    """Compile the conversation's task and prepare a Mission candidate. No mutation."""
    try:
        return conversation_handoff.propose(**body.model_dump())
    except Exception as exc:
        logger.exception("conversation propose failed")
        return {"ok": False, "operation": "conversation_propose", "error": str(exc)}


@router.post("/builder/conversation/approve")
def approve_builder_job(body: ApproveRequest) -> dict:
    """Create the durable Builder job. Refuses unless ``confirmed`` is explicitly true."""
    try:
        return conversation_handoff.approve(**body.model_dump())
    except Exception as exc:
        logger.exception("conversation approve failed")
        return {"ok": False, "operation": "conversation_approve", "error": str(exc)}


@router.get("/builder/conversation/resume")
def resume_builder_job(mission_id: str | None = None, task_id: str | None = None) -> dict:
    """Recover durable job state for a reloaded conversation, no transcript required."""
    try:
        return conversation_handoff.resume(mission_id=mission_id, task_id=task_id)
    except Exception as exc:
        logger.exception("conversation resume failed")
        return {"ok": False, "operation": "resume_context", "error": str(exc)}
