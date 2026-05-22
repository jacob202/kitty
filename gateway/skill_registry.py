"""Skill Registry — discover, register, and invoke skills from disk.

Skills live in .agents/skills/<name>/SKILL.md or .agents/skills/<category>/<name>/SKILL.md with YAML frontmatter:
  ---
  name: skill-name
  description: what it does
  when_to_use: (optional) when the model should consider this skill
  model: (optional) preferred model
  allowed_tools: (optional) list of tool names
  ---

Public API:
  discover() -> list[dict]     Scan disk and return all skills
  get(name) -> dict | None     Get one skill by name
  search(query) -> list[dict]  Find skills matching a query
  invoke(name, context) -> str Render a skill's system prompt for injection
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from gateway.paths import PROJECT_ROOT

logger = logging.getLogger("kitty.skill_registry")

SKILL_ROOTS: list[Path] = [
    PROJECT_ROOT / ".agents" / "skills",
]

# In-memory cache after first scan
_registry: dict[str, dict] | None = None


def _yaml_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from markdown text (between --- delimiters)."""
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}

    raw = match.group(1)
    result: dict = {}
    for line in raw.split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if value.startswith("[") and value.endswith("]"):
                # Simple list parsing: [a, b, c]
                value = [
                    v.strip().strip('"').strip("'")
                    for v in value[1:-1].split(",")
                    if v.strip()
                ]
            result[key] = value
    return result


def _parse_skill_file(path: Path) -> dict | None:
    """Parse a SKILL.md file and return skill metadata dict."""
    try:
        text = path.read_text()
    except Exception as e:
        logger.warning("Failed to read skill file %s: %s", path, e)
        return None

    meta = _yaml_frontmatter(text)
    if not meta.get("name"):
        logger.warning("Skill file %s has no 'name' in frontmatter", path)
        return None

    return {
        "name": meta.get("name", ""),
        "description": meta.get("description", ""),
        "when_to_use": meta.get("when_to_use", ""),
        "model": meta.get("model"),
        "allowed_tools": meta.get("allowed_tools", []),
        "path": str(path),
        "content": text,
    }


def _scan_directories() -> list[dict]:
    """Scan all skill roots for SKILL.md files and parse them."""
    skills: list[dict] = []
    seen: set[str] = set()

    for root in SKILL_ROOTS:
        if not root.exists():
            continue
        for skill_file in root.rglob("SKILL.md"):
            parsed = _parse_skill_file(skill_file)
            if parsed and parsed["name"] not in seen:
                seen.add(parsed["name"])
                skills.append(parsed)

    return skills


def discover(force_refresh: bool = False) -> list[dict]:
    """Discover all skills from disk. Caches after first call."""
    global _registry
    if _registry is not None and not force_refresh:
        return list(_registry.values())

    skills = _scan_directories()
    _registry = {s["name"]: s for s in skills}
    logger.info("Skill registry: discovered %d skills", len(skills))
    return skills


def get(name: str) -> dict | None:
    """Get a single skill by name."""
    discover()  # ensure registry is populated
    return _registry.get(name) if _registry else None


def search(query: str) -> list[dict]:
    """Find skills matching a query (searches name + description)."""
    all_skills = discover()
    if not query:
        return all_skills

    q = query.lower()
    results = []
    for skill in all_skills:
        name = skill.get("name", "").lower()
        desc = skill.get("description", "").lower()
        when = skill.get("when_to_use", "").lower()
        if q in name or q in desc or q in when:
            results.append(skill)
    return results


def invoke(name: str, context: Optional[str] = None) -> dict:
    """Prepare a skill for invocation. Returns the skill data with a rendered prompt.

    This doesn't execute the skill — it returns the system prompt and metadata
    so the caller (context_builder or LLM) can inject it into the session.
    """
    skill = get(name)
    if not skill:
        return {"error": f"Skill not found: {name}"}

    prompt = skill.get("content", "")

    # Strip frontmatter for the actual prompt
    prompt = re.sub(r"^---\s*\n.*?\n---\s*\n", "", prompt, flags=re.DOTALL).strip()

    if context:
        prompt = f"{prompt}\n\nContext: {context}"

    return {
        "name": skill["name"],
        "description": skill["description"],
        "prompt": prompt,
        "model": skill.get("model"),
        "allowed_tools": skill.get("allowed_tools", []),
    }
