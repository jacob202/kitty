"""Deadline routes (P7, docs/packets/017)."""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from gateway import deadline_extractor, deadline_store, deadline_sweep, deadline_watch
from gateway.brief_scheduler import load_brief_timezone
from gateway.deadline_store import DeadlineNotFound

logger = logging.getLogger("kitty.routes.deadlines")

router = APIRouter(tags=["deadlines"])


def _handle(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except DeadlineNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except deadline_store.DeadlineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except deadline_extractor.DeadlineExtractorError as exc:
        logger.warning("deadline extraction failed: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/deadlines")
def get_deadlines(status: str | None = "open") -> dict:
    if status == "needs_jacob":
        return {"deadlines": deadline_store.list_needs_jacob()}
    return {"deadlines": deadline_store.list_open(status=status)}


@router.get("/deadlines/{deadline_id}")
def get_deadline(deadline_id: int) -> dict:
    deadline = _handle(deadline_store.get, deadline_id)
    if deadline is None:
        raise HTTPException(status_code=404, detail=f"no deadline with id {deadline_id}")
    return deadline


@router.post("/deadlines/{deadline_id}/close")
def close_deadline(deadline_id: int) -> dict:
    return _handle(deadline_store.close, deadline_id)


@router.post("/deadlines/sweep")
def post_sweep(push: bool = True) -> dict:
    report = deadline_sweep.sweep()
    if not push:
        return {
            **report,
            "escalated": 0,
            "escalation_failed": 0,
            "delivery_status": "not_requested",
            "delivery_message": "Deadline escalation was not requested.",
        }

    # Use the user's configured timezone to compute "today" for deadline checkpoints
    user_tz = load_brief_timezone()
    today = datetime.now(user_tz).date()
    escalation = deadline_watch.check_and_push(now=today, push_fn=_push)
    pushed = int(escalation.get("pushed", 0))
    failed = int(escalation.get("failed", 0))
    attempted = int(escalation.get("attempted", 0))
    quiet_hours_deferred = int(escalation.get("quiet_hours_deferred", 0))

    if attempted == 0:
        delivery_status = "nothing_due"
        delivery_message = "No new deadline warning was due."
    elif pushed == 0 and failed > 0:
        if quiet_hours_deferred > 0:
            delivery_status = "quiet_hours_deferred"
            delivery_message = (
                f"A deadline warning was due, but {quiet_hours_deferred} "
                f"deferred by quiet-hours policy. Try again after quiet hours end."
            )
        else:
            delivery_status = "source_unavailable"
            delivery_message = (
                "A deadline warning was due, but nothing was delivered. "
                "Check notification setup and try again."
            )
    elif failed > 0:
        delivery_status = "partial"
        delivery_message = (
            f"{pushed} deadline warning{'s' if pushed != 1 else ''} delivered; "
            f"{failed} could not be delivered."
        )
    else:
        delivery_status = "delivered"
        delivery_message = f"{pushed} deadline warning{'s' if pushed != 1 else ''} delivered."

    return {
        **report,
        "escalated": pushed,
        "escalation_failed": failed,
        "delivery_status": delivery_status,
        "delivery_message": delivery_message,
    }


def _push(message: str, *, title: str, kind: str, dedupe_key: str) -> dict:
    from gateway.push import push_to_jacob

    return push_to_jacob(message, title=title, kind=kind, dedupe_key=dedupe_key)
