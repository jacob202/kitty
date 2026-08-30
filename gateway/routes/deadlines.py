"""Deadline routes (P7, docs/packets/017)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from gateway import deadline_extractor, deadline_store, deadline_sweep
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
def post_sweep(push: bool = False) -> dict:
    report = deadline_sweep.sweep(push_fn=_push if push else None)
    return report


def _push(message: str, *, title: str, kind: str, dedupe_key: str) -> bool:
    from gateway.push import push_to_jacob

    return push_to_jacob(message, title=title, kind=kind, dedupe_key=dedupe_key)
