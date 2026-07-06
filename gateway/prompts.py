"""Central catalog of inline prompts that were previously scattered across
domain modules.

Why this exists: a handful of short system / user prompts lived inside
the modules that use them (``journal.py``, ``parts.py``,
``inventory.py``). This module is also the home for loading versioned,
on-disk prompts (soul, repair, health, research, code) via
``load_prompt`` — previously a separate ``prompt_loader`` module that
was a 25-line pass-through.

Why not promote them to disk files immediately: every inline prompt
here is short (one paragraph or a few lines), and keeping them as
Python constants makes diff review easier. Promoting to disk is a
follow-up once a prompt is being iterated on.

Contract for callers: import the constant directly. Do not edit the
string at the call site — change it here so the change is one diff.
"""

from __future__ import annotations

from functools import lru_cache

from gateway.paths import PROMPTS_DIR

# -----------------------------------------------------------------------------
# On-disk versioned prompts (formerly gateway/prompt_loader.py)
# -----------------------------------------------------------------------------

DOMAIN_TO_FILE = {
    "soul": "soul_v1.md",
    "repair": "repair_v1.md",
    "health": "health_v1.md",
    "research": "research_v1.md",
    "code": "code_v1.md",
}


@lru_cache(maxsize=10)
def load_prompt(domain: str) -> str:
    """Load and cache a versioned system prompt from /prompts/."""
    filename = DOMAIN_TO_FILE.get(domain, "soul_v1.md")
    path = PROMPTS_DIR / filename
    if not path.exists():
        fallback = PROMPTS_DIR / "soul_v1.md"
        if fallback.exists():
            return fallback.read_text()
        return "You are Kitty, a personal AI for Jacob Brizinski."
    return path.read_text()


# -----------------------------------------------------------------------------
# Journal prompts (formerly gateway/journal.py)
# -----------------------------------------------------------------------------

# Kitty's interviewer persona — curious journalist, not therapist.
JOURNAL_INTERVIEW_PROMPT = """\
You are conducting a journal interview with Jacob. Your job is to be a curious,
attentive interviewer — not a therapist. You are not trying to fix anything.

Rules:
- Ask ONE question at a time. Only ever one.
- Start casual and specific. Not "how are you feeling today."
- Reference things you know about Jacob when you can.
- Follow threads. If he mentions something interesting, go there first.
- Never announce you're journaling or interviewing. Just talk.
- When the conversation has enough material (typically 6–10 exchanges), close naturally."""

# Turns a transcript into a first-person entry in Jacob's voice.
JOURNAL_SYNTHESIS_PROMPT = """\
You have just conducted a journal interview with Jacob.
Synthesize the conversation into a journal entry written from his perspective.

Rules:
- Write AS Jacob, first person, his voice and phrasing.
- Capture specifics he actually said — not summaries or paraphrases.
- Keep his exact wording where it's vivid.
- One to three paragraphs, no headers, no bullet points.
- End where the conversation ended. No forced resolution.
- Do not add insights he didn't express himself.
- Do not editorialize."""


# -----------------------------------------------------------------------------
# Parts council prompt (formerly gateway/parts.py)
# -----------------------------------------------------------------------------

PARTS_COUNCIL_PROMPT = """
---
## Parts mode active

Before responding, work through your internal council:

Skeptic: [what's missing, wrong, or the strongest counterargument]
Champion: [the best case for Jacob's position or idea]
Pragmatist: [the smallest real next step]
Observer: [what's underneath — the emotional undercurrent, the thing under the question]
Where I land: [your actual answer]

Show all four parts, then your resolved position. Don't skip any.
""".strip()


# -----------------------------------------------------------------------------
# Vision inventory prompt (formerly gateway/inventory.py extract_parts_from_image)
# -----------------------------------------------------------------------------

INVENTORY_PHOTO_PROMPT = """Analyze this photo of electronic components (e.g., a parts bin, a bag of transistors, capacitors).
        Identify the parts and extract them into a structured JSON array.
        Return ONLY a raw JSON array of objects with these keys:
        - "part_number" (e.g., "2SC1400", leave blank if unknown)
        - "value" (e.g., "470uF 50V", "10k ohm 1/4W", leave blank if unknown)
        - "type" (e.g., "Transistor", "Capacitor", "Resistor")
        - "quantity" (integer, estimate if in a pile, exact if clearly countable)
        - "notes" (e.g., "Nichicon Gold Tune", "SMD", "Through-hole")

        Do not wrap the output in markdown blocks. Return only the JSON."""


# -----------------------------------------------------------------------------
# Catalog
# -----------------------------------------------------------------------------

#: name -> (constant, version-tag string)
#: Use ``get_prompt(name)`` for forward-compatible lookups (e.g., from config).
CATALOG: dict[str, tuple[str, str]] = {
    "journal.interview": (JOURNAL_INTERVIEW_PROMPT, "v1"),
    "journal.synthesis": (JOURNAL_SYNTHESIS_PROMPT, "v1"),
    "parts.council": (PARTS_COUNCIL_PROMPT, "v1"),
    "inventory.photo": (INVENTORY_PHOTO_PROMPT, "v1"),
}


def get_prompt(name: str) -> str:
    """Return the prompt text for ``name``.

    Raises ``KeyError`` for unknown names — callers should not be
    passing strings that aren't in ``CATALOG``. Use the constants
    directly when the name is known at compile time.
    """
    return CATALOG[name][0]


def get_prompt_version(name: str) -> str:
    """Return the version tag for ``name`` (e.g. ``"v1"``)."""
    return CATALOG[name][1]


def list_prompts() -> list[dict[str, str | int]]:
    """Return a summary of every cataloged prompt."""
    return [
        {"name": name, "version": version, "chars": len(text)}
        for name, (text, version) in CATALOG.items()
    ]


# -----------------------------------------------------------------------------
# Prompt templates catalog (formerly gateway/prompts_catalog.py)
# -----------------------------------------------------------------------------

_TEMPLATES: list[dict] = [
    {
        "id": "brainstorm",
        "title": "Brainstorm",
        "content": (
            "Help me brainstorm ideas for: [topic]\n\nConsider:\n"
            "- Different perspectives\n- pros and cons\n- Creative solutions"
        ),
        "category": "Creative",
        "icon": "\U0001f4a1",
    },
    {
        "id": "debug",
        "title": "Debug Code",
        "content": (
            "Help me debug this code:\n\n```\n[code]\n```\n\n"
            "Error/issue: [description]\n\nWhat's wrong?"
        ),
        "category": "Technical",
        "icon": "\U0001f527",
    },
    {
        "id": "summarize",
        "title": "Summarize",
        "content": ("Summarize the following text:\n\n[text]\n\nKey points:"),
        "category": "Analysis",
        "icon": "\U0001f4c4",
    },
    {
        "id": "rewrite",
        "title": "Rewrite",
        "content": (
            "Rewrite the following to be more concise:\n\n[text]\n\nTarget length: [optional]"
        ),
        "category": "Writing",
        "icon": "\u270d\ufe0f",
    },
    {
        "id": "explain",
        "title": "Explain",
        "content": (
            "Explain the following concept:\n\n[concept]\n\nLevel: [beginner/intermediate/advanced]"
        ),
        "category": "Learning",
        "icon": "\U0001f393",
    },
]


def list_templates(category: str | None = None) -> list[dict]:
    """Return every prompt template, optionally filtered by ``category``."""
    if not category:
        return list(_TEMPLATES)
    needle = category.strip().lower()
    return [t for t in _TEMPLATES if str(t.get("category", "")).lower() == needle]


def get_template(template_id: str) -> dict | None:
    """Return a single template by ``id``, or ``None`` when unknown."""
    for template in _TEMPLATES:
        if template.get("id") == template_id:
            return dict(template)
    return None
