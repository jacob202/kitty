"""Inbox triage endpoints (P2, docs/packets/002).

Sync handlers on purpose: a triage pass blocks on LLM calls, so FastAPI
should run it in its worker pool rather than on the event loop (same
reasoning as the /state routes).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from gateway import triage

router = APIRouter(tags=["inbox"])


@router.post("/inbox/triage")
def post_inbox_triage(limit: int = 25) -> dict:
    """Classify untriaged inbox entries. Returns counts per bucket."""
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    return triage.run_pass(limit=limit)


@router.get("/inbox/triaged")
def get_inbox_triaged(bucket: str | None = None, limit: int = 50) -> dict:
    """List triaged entries, newest first. Optional bucket filter."""
    if bucket is not None and bucket not in triage.BUCKETS:
        raise HTTPException(
            status_code=400,
            detail=f"bucket must be one of {', '.join(triage.BUCKETS)}",
        )
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    return {"entries": triage.list_triaged(bucket=bucket, limit=limit)}
