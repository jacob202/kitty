"""Idea-mine review endpoints (packet 024, phase 2).

List quarantined extraction items, change their review state, and hand
approved items to the inbox pipeline. Surfacing is gated by review state
(see ``gateway/idea_mine_store``), so nothing recovered from chat history
becomes always-on memory until Jacob approves it.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from gateway import idea_mine_store as store

logger = logging.getLogger("kitty.routes.idea_mine")

router = APIRouter(prefix="/idea-mine", tags=["idea-mine"])


@router.get("/review")
def get_review_queue(object_type: str | None = None, review: str | None = None) -> dict:
    """List extraction items awaiting (or having received) review."""
    if object_type is not None and object_type not in store.OBJECT_TYPES:
        raise HTTPException(status_code=400, detail=f"unknown object_type: {object_type}")
    if review is not None and review not in store.REVIEW_STATES:
        raise HTTPException(status_code=400, detail=f"unknown review state: {review}")
    return {"items": store.list_items(object_type=object_type, review=review)}


@router.get("/surfaceable")
def get_surfaceable() -> dict:
    """Items currently allowed to appear in future context (approved/edited)."""
    return {"items": store.surfaceable_items()}


@router.patch("/{item_id}/review")
def patch_review(item_id: int, review_state: str) -> dict:
    """Set an item's review state (unreviewed/approved/edited/rejected/keep_quiet)."""
    if review_state not in store.REVIEW_STATES:
        raise HTTPException(status_code=400, detail=f"unknown review state: {review_state}")
    if not store.set_review(item_id, review_state):
        raise HTTPException(status_code=404, detail="idea-mine item not found")
    return {"id": item_id, "user_review": review_state}


@router.post("/export")
def post_export(dry_run: bool = False) -> dict:
    """Hand approved items to the inbox → triage → knowledge pipeline."""
    exported = store.export_approved_to_inbox(dry_run=dry_run)
    return {"exported": exported, "dry_run": dry_run}
