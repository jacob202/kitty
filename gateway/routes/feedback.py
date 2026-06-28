"""User feedback and error logging endpoint."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List

from fastapi import APIRouter

from gateway.paths import DATA_DIR

router = APIRouter(tags=["feedback"])

FEEDBACK_LOG = DATA_DIR / "feedback.jsonl"
ERROR_LOG = DATA_DIR / "kitty_errors.jsonl"


def log_feedback(feedback: Dict[str, Any]) -> None:
    """Log user feedback."""
    try:
        FEEDBACK_LOG.parent.mkdir(parents=True, exist_ok=True)
        feedback["timestamp"] = time.time()
        with open(FEEDBACK_LOG, "a") as f:
            f.write(json.dumps(feedback) + "\n")
    except Exception:
        pass


def log_error(error: Dict[str, Any]) -> None:
    """Log an error."""
    try:
        ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        error["timestamp"] = time.time()
        with open(ERROR_LOG, "a") as f:
            f.write(json.dumps(error) + "\n")
    except Exception:
        pass


@router.post("/feedback")
async def submit_feedback(payload: Dict[str, Any]) -> Dict[str, bool]:
    """Submit user feedback."""
    log_feedback(payload)
    return {"ok": True}


@router.post("/error")
async def log_error_endpoint(payload: Dict[str, Any]) -> Dict[str, bool]:
    """Log a client-side error."""
    log_error(payload)
    return {"ok": True}


@router.get("/feedback/stats")
async def get_feedback_stats() -> Dict[str, Any]:
    """Get feedback statistics."""
    feedbacks: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    # Read feedback
    if FEEDBACK_LOG.exists():
        try:
            with open(FEEDBACK_LOG, "r") as f:
                for line in f:
                    try:
                        feedbacks.append(json.loads(line.strip()))
                    except (json.JSONDecodeError, ValueError):
                        continue
        except Exception:
            pass

    # Read errors
    if ERROR_LOG.exists():
        try:
            with open(ERROR_LOG, "r") as f:
                for line in f:
                    try:
                        errors.append(json.loads(line.strip()))
                    except (json.JSONDecodeError, ValueError):
                        continue
        except Exception:
            pass

    # Count by type
    feedback_types: Dict[str, int] = {}
    for fb in feedbacks:
        ftype = fb.get("type", "unknown")
        feedback_types[ftype] = feedback_types.get(ftype, 0) + 1

    error_types: Dict[str, int] = {}
    for e in errors:
        etype = e.get("error_type", "unknown")
        error_types[etype] = error_types.get(etype, 0) + 1

    return {
        "total_feedback": len(feedbacks),
        "total_errors": len(errors),
        "feedback_by_type": feedback_types,
        "errors_by_type": error_types,
        "recent_feedback": feedbacks[-10:],
        "recent_errors": errors[-10:],
    }
