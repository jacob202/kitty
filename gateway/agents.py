"""Agents.md Persona System — Load and parse agent role definitions.

This module loads specialized agent personas from .agents/agents.md or .kitty/agents.md,
similar to Antigravity's agent team configuration.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

from gateway.paths import PROJECT_ROOT

logger = logging.getLogger("kitty.agents")


def load_agents_definitions() -> Dict[str, dict]:
    """Load agent personas from .agents/agents.md or .kitty/agents.md."""
    for candidate in [".agents/agents.md", ".kitty/agents.md", "AGENTS.md"]:
        path = PROJECT_ROOT / candidate
        if path.exists():
            content = path.read_text()
            return parse_agents_md(content)
    return {}


def parse_agents_md(content: str) -> Dict[str, dict]:
    """Parse agents.md format: ## @rolename ... content."""
    agents = {}
    current_role = None
    current_content: list[str] = []

    for line in content.split("\n"):
        # Check for role header: ## @rolename
        if line.startswith("## ") and "@" in line:
            # Save previous role if exists
            if current_role:
                agents[current_role] = {
                    "role": current_role,
                    "prompt": "\n".join(current_content).strip(),
                }
            # Start new role
            role_part = line[3:].strip()  # Remove "## "
            current_role = role_part.lstrip("@").split()[0]  # Get @name, take first word
            current_content = []
        elif current_role:
            current_content.append(line)

    # Don't forget the last role
    if current_role:
        agents[current_role] = {
            "role": current_role,
            "prompt": "\n".join(current_content).strip(),
        }

    return agents


def get_agent_prompt(role: str) -> str:
    """Get the prompt for a specific agent role."""
    agents = load_agents_definitions()
    if role in agents:
        return agents[role]["prompt"]
    return ""


def get_agent(role: str) -> Optional[dict]:
    """Get agent definition by role name."""
    agents = load_agents_definitions()
    return agents.get(role)


def list_agents() -> list:
    """List all available agent roles."""
    agents = load_agents_definitions()
    return list(agents.keys())


# Cache for performance
_agents_cache: Optional[Dict[str, dict]] = None


def load_agents_cached() -> Dict[str, dict]:
    """Load agents with caching."""
    global _agents_cache
    if _agents_cache is None:
        _agents_cache = load_agents_definitions()
    return _agents_cache


def reload_agents() -> Dict[str, dict]:
    """Force reload agent definitions."""
    global _agents_cache
    _agents_cache = None
    return load_agents_definitions()
