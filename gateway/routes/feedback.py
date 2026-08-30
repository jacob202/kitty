"""User feedback and error logging endpoint — thin FastAPI wrapper."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from gateway import feedback

router = APIRouter(tags=["feedback"])


@router.post("/feedback")
async def submit_feedback(payload: Dict[str, Any]) -> Dict[str, bool]:
    """Submit user feedback."""
    feedback.log_feedback(payload)
    return {"ok": True}


@router.post("/error")
async def log_error_endpoint(payload: Dict[str, Any]) -> Dict[str, bool]:
    """Log a client-side error."""
    feedback.log_error(payload)
    return {"ok": True}


@router.get("/feedback/stats")
async def get_feedback_stats() -> Dict[str, Any]:
    """Get feedback statistics."""
    return feedback.get_feedback_stats()
