"""Selective personal-intelligence projection for Home."""
from __future__ import annotations

from fastapi import APIRouter

from gateway import intelligence_projection, magic_kitty

router = APIRouter(tags=["intelligence"])


@router.get("/intelligence")
def get_intelligence(limit: int = 3) -> dict:
    return intelligence_projection.build_projection(limit=limit)


@router.post("/intelligence/refresh-connections")
def refresh_connections() -> dict:
    magic_kitty.discover_connections(force=True)
    return intelligence_projection.build_projection(limit=3)
