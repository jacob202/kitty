"""Chronicle — session history analysis and personalized usage tips."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from gateway import chats_store, chronicle_service

router = APIRouter(tags=["chronicle"])


@router.get("/chronicle/tips")
def chronicle_tips() -> dict[str, Any]:
    """Analyze session history and return personalized usage tips.

    Reads the durable chat store and delegates analysis to
    :mod:`gateway.chronicle_service`, which is fully side-effect-free and
    independently testable.
    """
    chats = chats_store.list_chats()
    return chronicle_service.analyze(chats)
