"""Action-queue endpoints (P3, docs/packets/003).

Sync handlers on purpose: executing a T2 action blocks on osascript, so
FastAPI should run these in its worker pool (same reasoning as /state).

Exceptions from ``action_queue`` map to HTTP status here — the queue module
stays framework-free.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from gateway import action_grants, action_queue

router = APIRouter(tags=["actions"])


class ProposeRequest(BaseModel):
    source_kind: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    title: str = Field(min_length=1)
    preview: str = Field(min_length=1)
    source_id: str | None = None
    payload: dict = Field(default_factory=dict)
    scope_type: str = "global"
    scope_id: str = ""
    session_id: str | None = None
    estimated_cost_usd: float | None = None


class GrantRequest(BaseModel):
    """One standing user decision. Mirrors the four UI choices in issue #554.

    "Allow once" is not a grant — it is the existing per-action approve call.
    """

    capability: str = Field(min_length=1)
    decision: str = Field(min_length=1)
    granted_tier: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    scope_type: str = "global"
    scope_id: str = ""
    session_id: str | None = None
    expires_at: float | None = None
    budget_limit_usd: float | None = None


class RememberRequest(BaseModel):
    """How long an "always allow here" choice should last.

    Deliberately carries no capability, tier or scope: those are read off the
    approved action so the caller cannot widen what it is being granted.
    """

    expires_at: float | None = None
    session_only: bool = False


class ApproveRequest(BaseModel):
    remember: RememberRequest | None = None


def _handle(fn, *args, **kwargs):
    """Run a queue call, translating its typed errors to HTTP status codes."""
    try:
        return fn(*args, **kwargs)
    except (action_queue.TierViolation, action_queue.GrantDenied) as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except action_queue.ActionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (action_queue.ActionStateError, action_queue.ApprovalIdentityMismatch) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (action_queue.UnknownActionKind, action_queue.ActionPayloadError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _handle_grant(fn, *args, **kwargs):
    """Same, for the grant store's typed errors."""
    try:
        return fn(*args, **kwargs)
    except action_grants.GrantNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except action_grants.GrantValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/actions")
def get_actions(status: str | None = None, limit: int = 50) -> dict:
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    return {"actions": action_queue.list_actions(status=status, limit=limit)}


@router.post("/actions/propose")
def post_propose(payload: ProposeRequest) -> dict:
    return _handle(
        action_queue.propose,
        source_kind=payload.source_kind,
        kind=payload.kind,
        title=payload.title,
        preview=payload.preview,
        source_id=payload.source_id,
        payload=payload.payload,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        session_id=payload.session_id,
        estimated_cost_usd=payload.estimated_cost_usd,
    )


@router.post("/actions/{action_id}/approve")
def post_approve(action_id: int, payload: ApproveRequest | None = None) -> dict:
    """Approve this action, and optionally stop asking for ones like it.

    Body is optional, so existing callers that send none keep working. Sending
    ``{"remember": {...}}`` is the UI's "always allow here": it approves this
    proposal *and* records the standing grant, in that order. The grant is
    minted from the approved row, never from the request body — see
    :func:`action_grants.grant_from_approved_action`.

    The approve step commits durably and cannot be undone, so a *subsequent*
    failure to record the grant (e.g. a bad ``expires_at``) must never be
    reported as if approval itself had failed (COR-002) — the caller would
    see a top-level error, then retry ``/approve`` and get a confusing 409
    for an action already decided. Instead the approved action is returned
    with a ``grant_error`` field describing what the "remember" step could
    not do.
    """
    approved = _handle(action_queue.approve, action_id)
    remember = payload.remember if payload else None
    if remember is None:
        return approved
    try:
        grant = action_grants.grant_from_approved_action(
            approved,
            expires_at=remember.expires_at,
            session_only=remember.session_only,
        )
    except action_grants.GrantValidationError as exc:
        return {**approved, "grant_error": str(exc)}
    return {**approved, "grant": grant}


@router.post("/actions/{action_id}/reject")
def post_reject(action_id: int) -> dict:
    return _handle(action_queue.reject, action_id)


@router.post("/actions/{action_id}/execute")
def post_execute(action_id: int) -> dict:
    return _handle(action_queue.execute, action_id)


@router.get("/actions/grants")
def get_grants(capability: str | None = None, include_inactive: bool = False) -> dict:
    return {
        "grants": action_grants.list_grants(
            capability=capability, include_inactive=include_inactive
        )
    }


@router.get("/actions/{action_id}")
def get_action(action_id: int) -> dict:
    action = action_queue.get(action_id)
    if action is None:
        raise HTTPException(status_code=404, detail=f"no action with id {action_id}")
    return action


@router.post("/actions/grants")
def post_grant(payload: GrantRequest) -> dict:
    return _handle_grant(
        action_grants.create_grant,
        capability=payload.capability,
        decision=payload.decision,
        granted_tier=payload.granted_tier,
        reason=payload.reason,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        session_id=payload.session_id,
        expires_at=payload.expires_at,
        budget_limit_usd=payload.budget_limit_usd,
        created_by="gateway_client",
        user_confirmed=False,
    )


@router.delete("/actions/grants/{grant_id}")
def delete_grant(grant_id: int) -> dict:
    return _handle_grant(action_grants.revoke_grant, grant_id)
