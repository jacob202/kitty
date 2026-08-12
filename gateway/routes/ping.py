"""Simple health-check endpoint — returns {\"ok\": true}."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["ping"])


@router.get("/ping")
async def ping():
    """Lightweight liveness probe.

    Returns a static JSON body so load-balancers and orchestration can
    confirm the Gateway process is alive and serving requests.
    """
    return {"ok": True}
