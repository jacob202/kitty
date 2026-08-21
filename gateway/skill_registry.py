"""Skill Registry — discover, register, and invoke skills from disk.

Skills live in .agents/skills/<name>/SKILL.md or .agents/skills/<category>/<name>/SKILL.md with YAML frontmatter:
  ---
  name: skill-name
  description: what it does
  when_to_use: (optional) when the model should consider this skill
  model: (optional) preferred model
  allowed_tools: (optional) list of tool names
  ---

Frontmatter is parsed as real YAML, so nested lists/dicts and multi-line
values work. The Agent Skills spec spells the tools field `allowed-tools`
(hyphen); Kitty's own skills use `allowed_tools` (underscore). Both are
accepted on read so third-party skill bundles parse without edits.

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

import yaml

from gateway.paths import PROJECT_ROOT

logger = logging.getLogger("kitty.skill_registry")

SKILL_ROOTS: list[Path] = [
    PROJECT_ROOT / ".agents" / "skills",
]

# In-memory cache after first scan
_registry: dict[str, dict] | None = None


def _yaml_frontmatter_legacy(raw: str) -> dict:
    """Line-based frontmatter fallback for values that aren't valid YAML.

    Kitty's early skills sometimes carry an unquoted ``USE WHEN: ...`` clause
    inside ``description``, which is a real YAML syntax error (an unquoted
    colon-space mid-scalar). Rather than dropping those skills from discovery,
    fall back to the original single-colon-per-line parse.
    """
    result: dict = {}
    for line in raw.split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if value.startswith("[") and value.endswith("]"):
                value = [
                    v.strip().strip('"').strip("'")
                    for v in value[1:-1].split(",")
                    if v.strip()
                ]
            result[key] = value
    return result


def _yaml_frontmatter(text: str) -> dict:
    """Extract and parse YAML frontmatter from markdown text (between --- delimiters)."""
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}

    raw = match.group(1)
    try:
        result = yaml.safe_load(raw)
        if not isinstance(result, dict):
            result = _yaml_frontmatter_legacy(raw)
    except yaml.YAMLError:
        result = _yaml_frontmatter_legacy(raw)

    # Agent Skills spec spells this `allowed-tools`; Kitty's own skills use
    # `allowed_tools`. Normalize to the underscore form Kitty consumers read.
    if "allowed-tools" in result and "allowed_tools" not in result:
        result["allowed_tools"] = result.pop("allowed-tools")

    return result


def _to_str(value: object) -> str:
    """Coerce a frontmatter value to plain text; anything but a string is dropped.

    Real YAML can produce None/bool/list/dict where Kitty's string fields
    expect text (the old line parser always produced a string). Calling
    str() on an unexpected nested structure would re-walk it and can
    reproduce YAML alias/anchor amplification — a handful of anchors can
    expand to megabytes on re-serialization — so an unexpected shape becomes
    "" rather than being stringified.
    """
    return value if isinstance(value, str) else ""


def _to_str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _to_str_list(value: object) -> list[str]:
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return value
    return []


def _parse_skill_file(path: Path) -> dict | None:
    """Parse a SKILL.md file and return skill metadata dict."""
    try:
        text = path.read_text()
    except Exception as e:
        logger.warning("Failed to read skill file %s: %s", path, e)
        return None

    meta = _yaml_frontmatter(text)
    name = meta.get("name")
    if not isinstance(name, str) or not name.strip():
        logger.warning("Skill file %s has no valid 'name' string in frontmatter", path)
        return None

    return {
        "name": name,
        "description": _to_str(meta.get("description")),
        "when_to_use": _to_str(meta.get("when_to_use")),
        "model": _to_str_or_none(meta.get("model")),
        "allowed_tools": _to_str_list(meta.get("allowed_tools")),
        "license": _to_str_or_none(meta.get("license")),
        "compatibility": _to_str_or_none(meta.get("compatibility")),
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


def _triggers(skill: dict) -> list[str]:
    """Extract trigger phrases from a skill's `USE WHEN ...` clause + when_to_use."""
    desc = skill.get("description", "")
    phrases: list[str] = []
    m = re.search(r"USE WHEN[:\s]+(.*?)(?:NOT FOR|$)", desc, re.IGNORECASE | re.DOTALL)
    if m:
        phrases += [p.strip().strip(".").lower() for p in m.group(1).split(",")]
    when = skill.get("when_to_use", "")
    if when:
        phrases += [p.strip().lower() for p in when.split(",")]
    # Keep multi-word phrases — single words are too noisy to match on.
    return [p for p in phrases if len(p.split()) >= 2]


def suggest(message: str, limit: int = 1) -> list[dict]:
    """Return skills whose trigger phrases appear in the message, best match first."""
    if not message:
        return []
    lower = message.lower()
    scored: list[tuple[int, dict]] = []
    for skill in discover():
        hits = sum(1 for phrase in _triggers(skill) if phrase in lower)
        if hits:
            scored.append((hits, skill))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [s for _, s in scored[:limit]]


def invoke(name: str, context: Optional[str] = None) -> dict:
    """Prepare a skill for invocation. Returns the skill data with a rendered prompt.

    This doesn't execute the skill — it returns the system prompt and metadata
    so the caller (context assembler or LLM) can inject it into the session.
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
