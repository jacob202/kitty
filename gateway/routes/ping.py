"""Simple health-check endpoint — returns {\"ok\": true} on GET /ping."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["ping"])


@router.get("/ping")
async def ping() -> dict:
    """Lightweight liveness probe."""
    return {"ok": True}
