"""User identity context — loads Jacob's TELOS files for prompt injection.

This is the counterpart to ``config/SOUL.md`` (which defines who *Kitty* is):
``config/USER/*.md`` describes who *Jacob* is — mission, goals, problems, beliefs,
wisdom, projects, mental models, narratives.

Files ship as templates carrying a ``TEMPLATE:`` marker line. A file is only
included once that marker is removed (i.e. once Jacob has actually filled it in),
so an unconfigured checkout injects nothing.

Public API:
    load_user_context() -> str   Compact "About Jacob (TELOS)" block, or "".
"""
from __future__ import annotations

from functools import lru_cache

from gateway.paths import USER_DIR

# Order files are presented in the prompt — index first, then most-actionable.
_ORDER = [
    "MISSION.md",
    "GOALS.md",
    "PROBLEMS.md",
    "PROJECTS.md",
    "BELIEFS.md",
    "WISDOM.md",
    "MODELS.md",
    "NARRATIVES.md",
]

_TEMPLATE_MARKER = "TEMPLATE:"


@lru_cache(maxsize=1)
def load_user_context() -> str:
    """Concatenate filled-in TELOS files into one prompt block.

    Skips files that are missing, empty, or still carry the TEMPLATE marker.
    Returns "" when nothing is configured.
    """
    if not USER_DIR.exists():
        return ""

    sections: list[str] = []
    for name in _ORDER:
        path = USER_DIR / name
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if not text or _TEMPLATE_MARKER in text:
            continue
        sections.append(text)

    if not sections:
        return ""

    body = "\n\n".join(sections)
    return f"## About Jacob (TELOS)\n\n{body}"
