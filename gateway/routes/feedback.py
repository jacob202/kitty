"""User feedback and error logging endpoint — thin FastAPI wrapper."""


from __future__ import annotations
from pydantic import BaseModel

from typing import Any, Dict

from fastapi import APIRouter

from gateway import feedback

class FeedbackFeedbackResponse(BaseModel):
    model_config = {"extra": "allow"}


class FeedbackErrorResponse(BaseModel):
    model_config = {"extra": "allow"}


class FeedbackFeedbackStatsResponse(BaseModel):
    model_config = {"extra": "allow"}



router = APIRouter(tags=["feedback"])


@router.post("/feedback", response_model=FeedbackFeedbackResponse)
async def submit_feedback(payload: Dict[str, Any]) -> Dict[str, bool]:
    """Submit user feedback."""
    feedback.log_feedback(payload)
    return {"ok": True}


@router.post("/error", response_model=FeedbackErrorResponse)
async def log_error_endpoint(payload: Dict[str, Any]) -> Dict[str, bool]:
    """Log a client-side error."""
    feedback.log_error(payload)
    return {"ok": True}


@router.get("/feedback/stats", response_model=FeedbackFeedbackStatsResponse)
async def get_feedback_stats() -> Dict[str, Any]:
    """Get feedback statistics."""
    return feedback.get_feedback_stats()
