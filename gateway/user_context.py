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


# --- Interview: conversationally fill the TELOS files ---

_LABELS = {
    "MISSION.md": "mission (the single through-line)",
    "GOALS.md": "goals (short- and long-term)",
    "PROBLEMS.md": "problems he's actively solving",
    "PROJECTS.md": "current projects",
    "BELIEFS.md": "core beliefs and values",
    "WISDOM.md": "hard-won lessons",
    "MODELS.md": "mental models he reasons with",
    "NARRATIVES.md": "recurring framings/stories",
}

_TRIGGERS = (
    "set up my telos",
    "fill in my telos",
    "fill my telos",
    "build my telos",
    "interview me",
    "telos interview",
    "tell you about myself",
    "set up my profile",
)


def _is_filled(path) -> bool:
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    return bool(text) and _TEMPLATE_MARKER not in text


def missing_sections() -> list[str]:
    """Filenames of TELOS sections still empty or carrying the template marker."""
    return [name for name in _ORDER if not _is_filled(USER_DIR / name)]


def is_interview_trigger(message: str) -> bool:
    lower = (message or "").lower()
    return any(t in lower for t in _TRIGGERS)


def update_section(name: str, content: str) -> bool:
    """Write a TELOS section file (creates USER_DIR if needed). Returns success."""
    fname = name if name.endswith(".md") else f"{name.upper()}.md"
    if fname not in _ORDER and fname != "TELOS.md":
        return False
    try:
        USER_DIR.mkdir(parents=True, exist_ok=True)
        (USER_DIR / fname).write_text(content.rstrip() + "\n", encoding="utf-8")
    except OSError:
        return False
    load_user_context.cache_clear()
    return True


def build_interview_prompt(base: str) -> str:
    """Append TELOS-interview instructions to a base system prompt."""
    missing = missing_sections()
    if missing:
        next_label = _LABELS.get(missing[0], missing[0])
        todo = ", ".join(_LABELS.get(m, m) for m in missing)
        focus = (
            f"The next unfilled section is **{missing[0]}** — {next_label}. "
            f"Still to cover: {todo}."
        )
    else:
        focus = "All TELOS sections are filled — offer to deepen or revise any of them."

    return (
        f"{base}\n\n"
        "## TELOS Interview Mode\n"
        "You are interviewing Jacob to build his TELOS (personal-identity context). "
        "Ask ONE focused question at a time — never dump a list of questions. "
        "Start from where he is; follow up to get specifics. "
        f"{focus}\n"
        "When you have enough for a section, emit it as a fenced markdown block "
        "labelled with the filename (e.g. ```MISSION.md ... ```) so it can be saved "
        "via POST /telos/{section}, then move to the next section."
    )

