"""Kitty ImageGuidance Bank — curated generation guidance as versioned Markdown.

Adapted from GenEvolve's KnowledgeTool / SkillBank pattern
(``genevolve/knowledge_tool.py:19-113``).  Kitty's version is local-first:
guidance is plain Markdown under a configured directory, loaded once at
import time, and never fetched from an external source.

Pointers:
  - this module was renamed from ``image_guidance.py`` to ``image_guidance_bank.py``
  - ``GuidanceBank`` is the static bank of curated generation-guidance Markdown files;
    each ``<tag>.md`` file contains expert prompt-writing or composition guidance
    for one proven failure category (layout, text rendering, count accuracy, etc.).
  - ``available_guidance_tags()`` and ``get_guidance()`` are the public API;
    they route through the singleton ``_guidance_bank`` instance.
  - The guidance directory default was updated from ``image_guidance`` to
    ``image_guidance_bank`` to match the new module filename.
"""

from __future__ import annotations

from pathlib import Path

# Default guidance directory — ship only the tags we have evidence for.
_DEFAULT_GUIDANCE_DIR = Path(__file__).resolve().parent / "image_guidance_bank"
_DEFAULT_GUIDANCE_DIR.mkdir(parents=True, exist_ok=True)


class GuidanceBank:
    """Static bank of curated generation-guidance Markdown files.

    Each file is named ``<tag>.md`` and contains expert prompt-writing
    or composition guidance for one proven failure category (layout,
    text rendering, count accuracy, etc.).
    """

    def __init__(self, guidance_dir: str | None = None) -> None:
        root = Path(guidance_dir).resolve() if guidance_dir else _DEFAULT_GUIDANCE_DIR
        self._root = root
        self._entries: dict[str, str] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    @property
    def root(self) -> Path:
        return self._root

    def available(self) -> list[str]:
        """Return sorted list of tag names with loaded guidance."""
        return sorted(self._entries.keys())

    def get(self, tag: str) -> str | None:
        """Return the Markdown content for *tag*, or None if unknown."""
        return self._entries.get(tag)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._root.exists():
            return
        for md_path in sorted(self._root.glob("*.md")):
            tag = md_path.stem
            self._entries[tag] = md_path.read_text(encoding="utf-8")


# Singleton used by the plan module and route handlers.
_guidance_bank = GuidanceBank()


def get_guidance_bank() -> GuidanceBank:
    return _guidance_bank


def available_guidance_tags() -> list[str]:
    return _guidance_bank.available()


def get_guidance(tag: str) -> str | None:
    return _guidance_bank.get(tag)
