"""Skill command registry — scans skill directories and provides lookup."""

from __future__ import annotations

import logging
import re
from functools import cache
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)

# Project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Skill directories to scan (relative to project root)
_SKILL_DIRS = [
    "src/tools/superpowers/skills",
    "consolidated-skills",
]

# Optional legacy archive (not in active config, but available by request)
_ARCHIVE_DIR = "archive/skills/legacy-skills"


class SkillEntry(TypedDict):
    name: str
    command: str
    description: str
    content: str
    path: str
    archived: bool | None


def _parse_frontmatter(content: str) -> dict[str, str]:
    """Parse YAML-like frontmatter from SKILL.md."""
    meta: dict[str, str] = {}
    m = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if m:
        for line in m.group(1).strip().splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                meta[key.strip()] = val.strip().strip('"')
    return meta


def _register_skill(
    registry: dict[str, SkillEntry],
    entry: Path,
    *,
    archived: bool = False,
) -> None:
    """Read a skill directory's SKILL.md and add it to the registry."""
    skill_md = entry / "SKILL.md"
    if not skill_md.exists():
        return
    content = skill_md.read_text(encoding="utf-8")
    meta = _parse_frontmatter(content)
    cmd = entry.name
    registry[cmd] = SkillEntry(
        name=meta.get("name", cmd),
        command=cmd,
        description=meta.get("description", ""),
        content=content,
        path=str(skill_md),
        archived=archived or None,
    )


def _scan_directory(
    directory: Path,
    registry: dict[str, SkillEntry],
    *,
    archived: bool = False,
) -> None:
    """Scan a single directory for skill subdirectories."""
    if not directory.exists():
        logger.debug("Skill directory not found: %s", directory)
        return
    for entry in sorted(directory.iterdir()):
        if entry.is_dir():
            _register_skill(registry, entry, archived=archived)


@cache
def _load_skills() -> tuple[dict[str, SkillEntry], dict[str, str]]:
    """Scan all skill directories and build the registry + case-insensitive lookup.

    Returns (registry, name_lookup) where name_lookup maps lowercase names
    to their canonical command keys.
    """
    registry: dict[str, SkillEntry] = {}

    for rel_dir in _SKILL_DIRS:
        _scan_directory(_PROJECT_ROOT / rel_dir, registry)

    archive_dir = _PROJECT_ROOT / _ARCHIVE_DIR
    if archive_dir.exists():
        _scan_directory(archive_dir, registry, archived=True)

    # Precompute case-insensitive lookup table
    name_lookup: dict[str, str] = {}
    for cmd_key, entry in registry.items():
        name_lookup[cmd_key.lower()] = cmd_key
        name_lookup[entry["name"].lower()] = cmd_key

    return registry, name_lookup


def get_skill(name: str) -> SkillEntry | None:
    """Look up a skill by command name or display name (case-insensitive)."""
    registry, name_lookup = _load_skills()

    if name in registry:
        return registry[name]

    canonical = name_lookup.get(name.lower())
    return registry.get(canonical) if canonical else None


def list_skills() -> dict[str, SkillEntry]:
    """Return all registered skills."""
    registry, _ = _load_skills()
    return dict(registry)


def format_skill_for_display(info: SkillEntry) -> str:
    """Format a skill entry for terminal output."""
    archived = info.get("archived", False)
    tag = " [dim](archived)[/dim]" if archived else ""
    cmd = f"[bold green]/{info['command']}[/bold green]"
    desc = info["description"] or "[dim]no description[/dim]"
    return f"  {cmd:32s} {desc}{tag}"
