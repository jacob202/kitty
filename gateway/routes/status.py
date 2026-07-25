"""Status glance endpoint — for Apple Watch / quick health checks."""

from __future__ import annotations
from pydantic import BaseModel

import json
import logging
import subprocess

from fastapi import APIRouter

class GlanceResponse(BaseModel):
    branch: str
    uncommitted: int
    tests: int


from gateway.paths import DATA_DIR, ROOT

logger = logging.getLogger("kitty.status")
router = APIRouter(tags=["status"])

_TEST_CACHE = DATA_DIR / "test-status.json"


def _git(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(
            ["git", *cmd],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=3,
        ).strip()
    except Exception:
        logger.debug("git %s failed", " ".join(cmd), exc_info=True)
        return "unknown"


def _test_status() -> str:
    try:
        return json.loads(_TEST_CACHE.read_text())["summary"]
    except Exception:
        logger.debug("reading test status cache failed", exc_info=True)
        return "unknown"


@router.get("/status/glance", response_model=GlanceResponse)
async def status_glance():
    """Quick read-only health snapshot for watch face / status bar."""
    branch = _git(["branch", "--show-current"])
    uncommitted = len(_git(["status", "--porcelain"]).splitlines()) if branch != "unknown" else -1
    return {
        "branch": branch,
        "uncommitted": uncommitted,
        "tests": _test_status(),
    }
