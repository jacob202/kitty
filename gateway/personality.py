"""Personality — load and assemble Kitty's modular personality files.

Three files in ``PERSONALITY_DIR`` define Kitty's identity:

- **soul.md** — core identity, intellectual mission, internal parts,
  communication style, behavioral boundaries
- **identity.md** — relationship with Jacob, how Kitty pays attention,
  memory philosophy, how she grows
- **agents.md** — how specialists, skills, MCP servers, and tools relate
  to Kitty as the central agent

Public API:
  personality_block() -> str     Joined markdown of all 3 files, cached
  get_personality_files() -> dict  Raw file contents keyed by name
"""

from __future__ import annotations

import logging
from pathlib import Path

from gateway.paths import PERSONALITY_DIR

logger = logging.getLogger("kitty.personality")

_PERSONALITY_FILES: dict[str, str] | None = None

_FILE_NAMES = ["soul.md", "identity.md", "agents.md"]


def _read_file(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8").strip()
        if text:
            return text
    except FileNotFoundError:
        logger.warning("Personality file not found: %s", path)
    except Exception as e:
        logger.warning("Failed to read personality file %s: %s", path, e)
    return ""


def _build_block(content: str) -> str:
    if not content:
        return ""
    return f"---\n{content}"


def _load_all() -> dict[str, str]:
    """Scan PERSONALITY_DIR and return {filename: content} for all 3 files."""
    result: dict[str, str] = {}
    for fname in _FILE_NAMES:
        path = PERSONALITY_DIR / fname
        content = _read_file(path)
        if content:
            result[fname] = content
    return result


def personality_block() -> str:
    """Return the joined personality markdown block for injection into the
    system prompt. Cached after first call. Returns an empty string when
    no personality files exist (safe no-op fallback)."""
    global _PERSONALITY_FILES
    if _PERSONALITY_FILES is None:
        _PERSONALITY_FILES = _load_all()

    blocks = []
    for content in _PERSONALITY_FILES.values():
        block = _build_block(content)
        if block:
            blocks.append(block)

    return "\n\n".join(blocks)


def get_personality_files() -> dict[str, str]:
    """Return {filename: content} for every loaded personality file.
    Used by the personality API route to serve read/edit endpoints."""
    global _PERSONALITY_FILES
    if _PERSONALITY_FILES is None:
        _PERSONALITY_FILES = _load_all()
    return dict(_PERSONALITY_FILES)


def invalidate_cache() -> None:
    """Force re-read on the next call. Call after a personality file is
    written so the next request picks up changes without a restart."""
    global _PERSONALITY_FILES
    _PERSONALITY_FILES = None
    logger.info("Personality cache invalidated")


__all__ = [
    "personality_block",
    "get_personality_files",
    "invalidate_cache",
]
