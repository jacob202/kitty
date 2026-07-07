"""Read-only log tail for the UI terminal view.

Whitelisted file names only — the file param is a key, never a path,
so there is no traversal surface.
"""
from __future__ import annotations

from collections import deque

from fastapi import APIRouter, HTTPException, Query

from gateway.paths import LOGS_DIR

router = APIRouter(tags=["logs"])

_ALLOWED = {
    "gateway": "gateway.log",
    "litellm": "litellm.log",
    "ui": "ui.log",
}


@router.get("/logs/tail")
def logs_tail(
    file: str = Query("gateway"),
    lines: int = Query(100, ge=1, le=500),
) -> dict:
    """Last N lines of a whitelisted log file."""
    name = _ALLOWED.get(file)
    if name is None:
        raise HTTPException(status_code=400, detail=f"unknown log: {file}")
    path = LOGS_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{name} not found")
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        tail = deque(fh, maxlen=lines)
    return {"file": name, "lines": [line.rstrip("\n") for line in tail]}
