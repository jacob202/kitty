"""Unified read-only activity projection for the Kitty product shell."""

from fastapi import APIRouter, Query

from gateway.activity_projection import build_activity_projection

router = APIRouter(tags=["activity"])


@router.get("/activity")
def get_activity(limit: int = Query(default=40, ge=1, le=100)) -> dict:
    return build_activity_projection(limit=limit)
