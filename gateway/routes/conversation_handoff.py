"""HTTP surface for the conversation -> approved KittyBuilder job handoff.

Mirrors the KittyBuilder MCP bridge's propose/approve/resume contract
(``mcp/builder``) so Kitty's native chat UI and any MCP client share one
approval mechanism and one durable authority. See
``gateway/conversation_handoff.py`` for the delegation this wraps.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from gateway import conversation_handoff, mission_runtime

logger = logging.getLogger("kitty.conversation_handoff_routes")
router = APIRouter(tags=["conversation-handoff"])


class CompileRequest(BaseModel):
    request: str = Field(min_length=1, max_length=8000)
    allow_provider_fallback: bool = False


class ProposeRequest(BaseModel):
    objective: str = Field(min_length=1, max_length=2000)
    instructions: str = Field(min_length=1, max_length=8000)
    allowed_paths: list[str] = Field(min_length=1)
    initiative_id: str | None = None
    title: str | None = None
    acceptance_criteria: list[str] | None = None
    validation_commands: list[str] | None = None
    # Where the request came from. Stored on the Mission at binding so the
    # result can be recovered without the browser holding the only copy.
    conversation_id: str | None = None
    message_id: str | None = None
    project_id: int | None = None


class ApproveRequest(BaseModel):
    prepared_manifest: dict
    expected_manifest_sha: str
    expected_base_sha: str
    approval_nonce: str
    gateway_mission_id: str | None = None
    confirmed: bool = False


@router.post("/builder/conversation/compile")
def compile_builder_request(body: CompileRequest) -> dict:
    """Shape plain language into one bounded Builder task. No Builder mutation."""
    try:
        return conversation_handoff.compile_request(
            body.request, allow_provider_fallback=body.allow_provider_fallback
        )
    except Exception:
        logger.exception("conversation compile failed")
        return {
            "ok": False,
            "operation": "conversation_compile",
            "error": "Kitty could not prepare the proposal right now. Try again in a moment.",
        }


@router.post("/builder/conversation/propose")
def propose_builder_job(body: ProposeRequest, background_tasks: BackgroundTasks) -> dict:
    """Prepare one Mission candidate and automatically request independent plan review."""
    try:
        result = conversation_handoff.propose(**body.model_dump())
        gateway_mission_id = result.get("gateway_mission_id") if result.get("ok") else None
        if isinstance(gateway_mission_id, str) and gateway_mission_id:
            background_tasks.add_task(mission_runtime.request_plan_review, gateway_mission_id)
        return result
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
        return conversation_handoff.approve(**body.model_dump())
    except Exception:
        logger.exception("conversation approve failed")
        return {
            "ok": False,
            "operation": "conversation_approve",
            "error": "Kitty could not create the Builder job right now. Try again in a moment.",
        }


@router.get("/builder/conversation/resume")
def resume_builder_job(
    background_tasks: BackgroundTasks,
    mission_id: str | None = None,
    task_id: str | None = None,
) -> dict:
    """Recover durable state and reconcile a finished Builder result into Mission."""
    try:
        result = conversation_handoff.resume(mission_id=mission_id, task_id=task_id)
        acceptance = result.get("mission_acceptance") if isinstance(result, dict) else None
        gateway_mission_id = acceptance.get("mission_id") if isinstance(acceptance, dict) else None
        # Gate on the exact Builder/Mission facts, not the aggregate receipt.
        # `ok: false` can mean an unrelated cold-start source is degraded while
        # these three fields are still authoritative. Startup recovery is
        # one-shot and may have run before the task finished, so suppressing
        # reconciliation here would leave the reviewed result unbound — and the
        # Mission unacceptable — for as long as the unrelated failure persists.
        if (
            isinstance(result, dict)
            and result.get("builder_task_complete") is True
            and result.get("awaiting_acceptance") is True
            and isinstance(gateway_mission_id, str)
            and gateway_mission_id
        ):
            background_tasks.add_task(
                mission_runtime.reconcile_result_candidate_background, gateway_mission_id
            )
        return result
    except Exception:
        logger.exception("conversation resume failed")
        return {
            "ok": False,
            "operation": "resume_context",
            "error": "Kitty could not recover this job's current state right now. Reload and try again.",
        }
