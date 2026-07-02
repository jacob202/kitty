"""Action-queue endpoints (P3, docs/packets/003).

Sync handlers on purpose: executing a T2 action blocks on osascript, so
FastAPI should run these in its worker pool (same reasoning as /state).

Exceptions from ``action_queue`` map to HTTP status here — the queue module
stays framework-free.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from gateway import action_queue

router = APIRouter(tags=["actions"])


class ProposeRequest(BaseModel):
    source_kind: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    title: str = Field(min_length=1)
    preview: str = Field(min_length=1)
    source_id: str | None = None
    payload: dict = Field(default_factory=dict)


def _handle(fn, *args, **kwargs):
    """Run a queue call, translating its typed errors to HTTP status codes."""
    try:
        return fn(*args, **kwargs)
    except action_queue.TierViolation as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except action_queue.ActionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except action_queue.ActionStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (action_queue.UnknownActionKind, action_queue.ActionPayloadError) as exc:
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
    )


@router.post("/actions/{action_id}/approve")
def post_approve(action_id: int) -> dict:
    return _handle(action_queue.approve, action_id)


@router.post("/actions/{action_id}/reject")
def post_reject(action_id: int) -> dict:
    return _handle(action_queue.reject, action_id)


@router.post("/actions/{action_id}/execute")
def post_execute(action_id: int) -> dict:
    return _handle(action_queue.execute, action_id)
