"""Prompt templates endpoint for Kitty UI."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["prompts"])

# Sample prompt templates (would be persisted in production)
_templates = [
    {
        "id": "brainstorm",
        "title": "Brainstorm",
        "content": "Help me brainstorm ideas for: [topic]\n\nConsider:\n- Different perspectives\n- pros and cons\n- Creative solutions",
        "category": "Creative",
        "icon": "💡",
    },
    {
        "id": "debug",
        "title": "Debug Code",
        "content": "Help me debug this code:\n\n```\n[code]\n```\n\nError/issue: [description]\n\nWhat's wrong?",
        "category": "Technical",
        "icon": "🔧",
    },
    {
        "id": "summarize",
        "title": "Summarize",
        "content": "Summarize the following text:\n\n[text]\n\nKey points:",
        "category": "Analysis",
        "icon": "📄",
    },
    {
        "id": "rewrite",
        "title": "Rewrite",
        "content": "Rewrite the following to be more concise:\n\n[text]\n\nTarget length: [optional]",
        "category": "Writing",
        "icon": "✍️",
    },
    {
        "id": "explain",
        "title": "Explain",
        "content": "Explain the following concept:\n\n[concept]\n\nLevel: [beginner/intermediate/advanced]",
        "category": "Learning",
        "icon": "🎓",
    },
]


@router.get("/prompts")
async def get_prompts(category: str | None = None):
    """Get prompt templates, optionally filtered by category."""
    if category:
        filtered = [t for t in _templates if t.get("category", "").lower() == category.lower()]
        return {"templates": filtered}
    return {"templates": _templates}
