"""Current-state endpoints (P1) — composed read, snapshot, mechanical diff.

Sync handlers on purpose: compose_now blocks on a bounded thread fan-out,
so FastAPI should run these in its worker pool, not on the event loop.
"""

from __future__ import annotations
from pydantic import BaseModel

from fastapi import APIRouter

from gateway import state_composer

class StateStateNowResponse(BaseModel):
    model_config = {"extra": "allow"}


class StateStateSnapshotResponse(BaseModel):
    model_config = {"extra": "allow"}


class StateStateChangesResponse(BaseModel):
    model_config = {"extra": "allow"}



router = APIRouter(tags=["state"])


@router.get("/state/now", response_model=StateStateNowResponse)
def state_now() -> dict:
    """Composed current state. Read-only, no side effects."""
    return state_composer.compose_now()


@router.post("/state/snapshot", response_model=StateStateSnapshotResponse)
def state_snapshot() -> dict:
    """Persist the current state as the new diff baseline."""
    return state_composer.snapshot_now()


@router.get("/state/changes", response_model=StateStateChangesResponse)
def state_changes() -> dict:
    """Diff current state vs the latest snapshot, plus signals since."""
    return state_composer.changes_since_snapshot()
