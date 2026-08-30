"""Expose the durable session handoff in a small dashboard-friendly shape."""

from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi import APIRouter

from gateway.paths import ROOT

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


def _live_branch() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=2,
    )
    branch = result.stdout.strip()
    if not branch:
        raise RuntimeError("git returned an empty current branch")
    return branch


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
    return {
        "current_branch": _live_branch(),
        "last_session_topic": _last_session_topic(state_sections),
        "open_threads": open_threads,
        "next_actions": next_actions,
    }
