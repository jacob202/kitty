"""Status glance endpoint — for Apple Watch / quick health checks."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(tags=["status"])

_TEST_CACHE = Path(__file__).parent.parent.parent / "data" / "test-status.json"


def _git(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(
            ["git", *cmd],
            cwd=Path(__file__).parent.parent.parent,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=3,
        ).strip()
    except Exception:
        return "unknown"


def _test_status() -> str:
    try:
        return json.loads(_TEST_CACHE.read_text())["summary"]
    except Exception:
        return "unknown"


@router.get("/status/glance")
async def status_glance():
    """Fast read-only snapshot for watch face / status bar."""
    branch = _git(["branch", "--show-current"])
    uncommitted = len(_git(["status", "--porcelain"]).splitlines()) if branch != "unknown" else -1
    return {
        "branch": branch,
        "uncommitted": uncommitted,
        "tests": _test_status(),
    }
