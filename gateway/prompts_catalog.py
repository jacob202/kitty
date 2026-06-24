"""Read-only catalog of prompt templates surfaced by ``/prompts``.

Why this module exists (Phase 3 of the gateway deepening program):
the route used to hardcode its own copy of the template list, a
plain "route as island" pattern. The list is now the canonical
source of truth, owned by this module, and the route is a thin
filter wrapper.
"""

from __future__ import annotations

from typing import Optional

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
        "content": (
            "Summarize the following text:\n\n[text]\n\nKey points:"
        ),
        "category": "Analysis",
        "icon": "\U0001f4c4",
    },
    {
        "id": "rewrite",
        "title": "Rewrite",
        "content": (
            "Rewrite the following to be more concise:\n\n[text]\n\n"
            "Target length: [optional]"
        ),
        "category": "Writing",
        "icon": "\u270d\ufe0f",
    },
    {
        "id": "explain",
        "title": "Explain",
        "content": (
            "Explain the following concept:\n\n[concept]\n\n"
            "Level: [beginner/intermediate/advanced]"
        ),
        "category": "Learning",
        "icon": "\U0001f393",
    },
]


def list_templates(category: Optional[str] = None) -> list[dict]:
    """Return every prompt template, optionally filtered by ``category``."""
    if not category:
        return list(_TEMPLATES)
    needle = category.strip().lower()
    return [t for t in _TEMPLATES if str(t.get("category", "")).lower() == needle]


def get_template(template_id: str) -> Optional[dict]:
    """Return a single template by ``id``, or ``None`` when unknown."""
    for template in _TEMPLATES:
        if template.get("id") == template_id:
            return dict(template)
    return None
