"""Read-only product Work snapshot derived from Builder status."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from gateway.builder_status import build_status_snapshot
from gateway.work_projection import project_work_snapshot

router = APIRouter(tags=["work"])


@router.get("/work")
def get_work() -> dict:
    """Return the bounded product Work snapshot from Builder state."""
    try:
        snapshot = build_status_snapshot()
    except Exception as exc:
        detail = str(exc).strip().replace("\n", " ")
        if len(detail) > 240:
            detail = detail[:239].rstrip() + "…"
        raise HTTPException(
            status_code=503,
            detail=f"Work snapshot unavailable: {type(exc).__name__}: {detail}",
        ) from exc
    return project_work_snapshot(snapshot)
