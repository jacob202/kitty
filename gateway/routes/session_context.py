"""Expose the durable session handoff in a small dashboard-friendly shape."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from fastapi import APIRouter

from gateway.paths import ROOT

logger = logging.getLogger("kitty.routes.session_context")

router = APIRouter(tags=["session"])

HANDOFF_FILE = ROOT / ".claude" / "HANDOFF.md"
STATE_FILE = ROOT / ".claude" / "STATE.md"


def _sections(path: Path) -> list[tuple[str, list[str]]]:
    """Read level-two markdown sections without guessing at their internal format."""
    document = path.read_text(encoding="utf-8")
    sections: list[tuple[str, list[str]]] = []
    heading: str | None = None
    lines: list[str] = []
    for line in document.splitlines():
        if line.startswith("## "):
            if heading is not None:
                sections.append((heading, lines))
            heading = line[3:].strip()
            lines = []
        elif heading is not None:
            lines.append(line)
    if heading is not None:
        sections.append((heading, lines))
    return sections


def _bullets(sections: list[tuple[str, list[str]]], heading: str) -> list[str]:
    for section_heading, lines in sections:
        if section_heading.casefold() == heading.casefold():
            return [line[2:].strip() for line in lines if line.startswith("- ")]
    return []


def _live_branch() -> tuple[str | None, str | None]:
    """Best-effort current branch plus a separate reason when the lookup fails.

    This is a read-only dashboard endpoint, so a missing git binary or a
    checkout that isn't a canonical repo (a container, a detached worktree, a
    packaged deployment) degrades the field to None instead of 500ing the whole
    session-context response. Degrading must not erase the difference between
    "git told us there is no branch" and "we never managed to ask git", so the
    failure also logs the exception and returns an operator-visible reason
    alongside the None."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning(
            "git rev-parse --abbrev-ref HEAD failed in %s: %s: %s",
            ROOT,
            type(exc).__name__,
            exc,
        )
        return None, (
            f"git rev-parse --abbrev-ref HEAD failed ({type(exc).__name__});"
            " see the gateway log for details"
        )
    branch = result.stdout.strip()
    return (branch or None), None


def _last_session_topic(state_sections: list[tuple[str, list[str]]]) -> str | None:
    state_text = STATE_FILE.read_text(encoding="utf-8")
    for line in state_text.splitlines():
        if line.startswith("# ") and not line.startswith("## "):
            topic = line[2:].strip()
            if topic:
                return topic
    return None


@router.get("/session/context")
def get_session_context() -> dict[str, str | list[str] | None]:
    """Return the current handoff topic, active threads, and explicit next actions."""
    handoff_sections = _sections(HANDOFF_FILE)
    state_sections = _sections(STATE_FILE)
    open_threads = _bullets(handoff_sections, "Resume here")
    next_actions = open_threads + _bullets(state_sections, "Next")
    current_branch, current_branch_error = _live_branch()
    return {
        "current_branch": current_branch,
        "current_branch_error": current_branch_error,
        "last_session_topic": _last_session_topic(state_sections),
        "open_threads": open_threads,
        "next_actions": next_actions,
    }
