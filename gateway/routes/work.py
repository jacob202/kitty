"""Work API routes — three read-only endpoints over the Work spine.

GET /work                         — list work items (state, source, limit filters)
GET /work/{work_id}               — single work item detail
GET /work/{work_id}/events        — work item events in chronological order

All data is projected from public Builder read APIs.  Builder is the only
v1 source of truth.  ``source`` is always ``"builder"``.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from gateway import work_spine as ws
from gateway.paths import BUILDER_QUEUE_DB

router = APIRouter(tags=["work"])


@router.get("/work")
def list_work(
    state: str | None = Query(None, description="Filter by normalized Work state"),
    source: str | None = Query(None, description='Must be "builder" in v1'),
    limit: int = Query(100, description="Maximum items to return (1-500)"),
) -> dict:
    """List work items from the Builder queue, optionally filtered.

    In v1 only ``source=builder`` is supported.  Results are ordered by
    Builder's default sort (state, priority, id).
    """
    try:
        campaign, items = ws.list_work(
            state=state, source=source, limit=limit, db_path=BUILDER_QUEUE_DB
        )
    except ws.WorkStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ws.WorkSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Unexpected Builder read failure: {type(exc).__name__}: "
            f"{str(exc)[:200]}",
        ) from exc
    campaign["items"] = items
    return campaign


@router.get("/work/{work_id}")
def get_work(work_id: str) -> dict:
    """Return a single work item with full detail.

    Returns 404 when the work ID does not exist.
    Returns 400 when the work ID prefix is unrecognised or the Builder
    task state is unknown.
    Returns 503 on unexpected Builder read failures.
    """
    try:
        item = ws.get_work(work_id, db_path=BUILDER_QUEUE_DB)
    except ws.WorkNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ws.WorkSourceError, ws.WorkStateError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Unexpected Builder read failure: {type(exc).__name__}: "
            f"{str(exc)[:200]}",
        ) from exc
    return item


@router.get("/work/{work_id}/events")
def get_work_events(work_id: str) -> dict:
    """Return all events for a work item in chronological order.

    Returns 404 when the work ID does not exist.
    Returns 400 when the work ID prefix is unrecognised.
    Returns 503 on unexpected Builder read failures.
    """
    try:
        events = ws.get_work_events(work_id, db_path=BUILDER_QUEUE_DB)
    except ws.WorkNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ws.WorkSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Unexpected Builder read failure: {type(exc).__name__}: "
            f"{str(exc)[:200]}",
        ) from exc
    return {"events": events}
