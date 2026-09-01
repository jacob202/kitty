"""Read-only product Work snapshot derived from Builder status."""

from __future__ import annotations

from dataclasses import asdict

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


@router.get("/work/{initiative_id}/why")
async def work_why(initiative_id: str):
    """Explain why a Builder work item has its current status.

    Uses only the existing Builder status/work projection. Returns the same
    ``Explanation`` fields as the schedule/action why endpoints: status, reason,
    relevant_at, action, automation, evidence, next_step.
    """
    from gateway.why_not import WorkNotFound, explain_work_item

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
    projected = project_work_snapshot(snapshot)
    try:
        return {"explanation": asdict(explain_work_item(projected, initiative_id))}
    except WorkNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
