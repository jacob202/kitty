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

# conversation_handoff.propose()/approve()/resume() carry a raw
# f"{type(exc).__name__}: {exc}" string in `error` for these codes -- useful
# for an MCP client's diagnostics, but a raw exception dump violates Kitty's
# user-facing-copy rule when this same receipt reaches the chat UI. Translate
# only what a person needs to know; the original text still reaches the logs.
_USER_FACING_ERROR_COPY: dict[str, str] = {
    "repo_unavailable": "Kitty could not reach the repository to prepare this job. Try again in a moment.",
    "planning_artifact_failed": "Kitty could not save this proposal's plan. Try again, or ask to resolve the coordination lock if this keeps happening.",
}


def _translate_receipt_error(result: dict) -> dict:
    if isinstance(result, dict) and result.get("ok") is False:
        code = result.get("error_code")
        safe_copy = _USER_FACING_ERROR_COPY.get(code) if isinstance(code, str) else None
        if safe_copy is not None:
            logger.warning("conversation handoff %s: %s", code, result.get("error"))
            result = {**result, "error": safe_copy}
    return result


class CompileRequest(BaseModel):
    request: str = Field(min_length=1, max_length=8000)


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


@router.post("/builder/conversation/compile")
def compile_builder_request(body: CompileRequest) -> dict:
    """Shape plain language into one bounded Builder task. No Builder mutation."""
    try:
        return conversation_handoff.compile_request(body.request)
    except Exception:
        logger.exception("conversation compile failed")
        return {
            "ok": False,
            "operation": "conversation_compile",
            "error": "Kitty could not prepare the proposal right now — no model provider is available. Try again in a moment.",
        }


@router.post("/builder/conversation/propose")
def propose_builder_job(body: ProposeRequest) -> dict:
    """Compile the conversation's task and prepare a Mission candidate. No mutation."""
    try:
        return _translate_receipt_error(conversation_handoff.propose(**body.model_dump()))
    except Exception:
        logger.exception("conversation propose failed")
        return {
            "ok": False,
            "operation": "conversation_propose",
            "error": "Kitty could not prepare this Builder job right now. Try again in a moment.",
        }


@router.post("/builder/conversation/approve")
def approve_builder_job(body: ApproveRequest) -> dict:
    """Create the durable Builder job. Refuses unless ``confirmed`` is explicitly true."""
    try:
        return _translate_receipt_error(conversation_handoff.approve(**body.model_dump()))
    except Exception:
        logger.exception("conversation approve failed")
        return {
            "ok": False,
            "operation": "conversation_approve",
            "error": "Kitty could not create the Builder job right now. Try again in a moment.",
        }


@router.get("/builder/conversation/resume")
def resume_builder_job(mission_id: str | None = None, task_id: str | None = None) -> dict:
    """Recover durable job state for a reloaded conversation, no transcript required."""
    try:
        return _translate_receipt_error(
            conversation_handoff.resume(mission_id=mission_id, task_id=task_id)
        )
    except Exception:
        logger.exception("conversation resume failed")
        return {
            "ok": False,
            "operation": "resume_context",
            "error": "Kitty could not recover this job's current state right now. Reload and try again.",
        }
