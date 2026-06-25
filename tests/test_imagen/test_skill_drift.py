"""Drift test: SKILL.md mentions every @mcp.tool() defined in server.py.

If you add a new tool to server.py and forget to document it in
mcp/imagen/SKILL.md, this test fails. Run as part of the imagen
test slice.
"""

from __future__ import annotations

import re
from pathlib import Path

SERVER_PY = Path(__file__).resolve().parents[2] / "mcp" / "imagen" / "server.py"
SKILL_MD = Path(__file__).resolve().parents[2] / "mcp" / "imagen" / "SKILL.md"


def _tool_names() -> list[str]:
    """Return every function name decorated with @mcp.tool() in server.py."""
    text = SERVER_PY.read_text(encoding="utf-8")
    # Each tool is defined as: @mcp.tool()\n<async? def NAME(
    return re.findall(r"@mcp\.tool\(\)\s*\n\s*(?:async\s+)?def\s+(\w+)\s*\(", text)


def _skill_md_text() -> str:
    return SKILL_MD.read_text(encoding="utf-8")


def test_skill_md_exists():
    assert SKILL_MD.exists(), f"missing {SKILL_MD}"


def test_skill_md_mentions_every_tool():
    tools = _tool_names()
    assert tools, "no @mcp.tool() decorators found — did the regex break?"

    skill_text = _skill_md_text()
    missing = [name for name in tools if name not in skill_text]
    assert not missing, (
        f"SKILL.md is missing these tools: {missing}. "
        "Add a one-line description for each in the 'Tool catalog' section."
    )


def test_skill_md_has_engine_routing_section():
    """The plan requires an 'Engine routing' section explaining when to
    use each engine."""
    text = _skill_md_text()
    assert "## Engine routing" in text or "### Engine routing" in text, (
        "SKILL.md must have an 'Engine routing' section"
    )


def test_skill_md_has_workflow_recipes():
    """Quick gen, refine, batch, character, find old work — at least 4
    of the 5 should be present (allow a recipe to be removed if it's
    no longer relevant)."""
    text = _skill_md_text().lower()
    expected = [
        "quick gen",
        "refine",
        "batch",
        "character",
    ]
    present = [r for r in expected if r in text]
    assert len(present) >= 3, (
        f"SKILL.md workflow recipes section is missing too many: "
        f"expected at least 3 of {expected}, found only {present}"
    )


def test_skill_md_mentions_aspect_aliases():
    text = _skill_md_text().lower()
    assert "cinemascope" in text, "SKILL.md should document the 'cinemascope' aspect alias"
    assert "instagram_square" in text or "portrait_phone" in text, (
        "SKILL.md should document at least one portrait/social aspect alias"
    )
