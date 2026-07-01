"""Current-state read endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from gateway import state_composer

router = APIRouter(tags=["state"])


@router.get("/state/now")
async def get_state_now():
    return state_composer.compose_now()
