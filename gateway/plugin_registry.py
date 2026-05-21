"""Plugin Registry — extensible capability system for Kitty.

Plugins bundle skills, hooks, and MCP servers into toggleable units.
Users enable/disable plugins via API, persisted to data/plugin_settings.json.

Pattern ported from free-code's plugins/builtinPlugins.ts.

Public API:
  register(definition) -> bool        Register a plugin
  list(enabled_only) -> list[dict]    List all plugins
  enable(name) -> bool                Enable a plugin
  disable(name) -> bool               Disable a plugin
  is_enabled(name) -> bool            Check if plugin is enabled
"""
from __future__ import annotations

import json
import logging
from typing import Optional, Callable

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.plugin_registry")

PLUGIN_SETTINGS = DATA_DIR / "plugin_settings.json"
_registry: dict[str, dict] = {}


# --- Plugin Definition ---

def register(
    name: str,
    description: str = "",
    version: str = "1.0.0",
    *,
    skills: Optional[list[dict]] = None,
    hooks: Optional[dict] = None,
    mcp_servers: Optional[list[dict]] = None,
    default_enabled: bool = True,
    is_available: Optional[Callable[[], bool]] = None,
) -> bool:
    """Register a plugin. Returns True if newly registered."""
    if name in _registry:
        logger.warning("Plugin already registered: %s", name)
        return False

    _registry[name] = {
        "name": name,
        "description": description,
        "version": version,
        "skills": skills or [],
        "hooks": hooks or {},
        "mcp_servers": mcp_servers or [],
        "default_enabled": default_enabled,
        "is_available": is_available,
    }
    logger.info("Plugin registered: %s v%s", name, version)
    return True


def list_plugins(enabled_only: bool = False) -> list[dict]:
    """List all registered plugins with their enabled state."""
    settings = _load_settings()
    plugins = []

    for name, definition in _registry.items():
        # Check availability
        if definition.get("is_available"):
            try:
                if not definition["is_available"]():
                    continue
            except Exception:
                continue

        user_setting = settings.get(name)
        enabled = user_setting if user_setting is not None else definition.get("default_enabled", True)

        if enabled_only and not enabled:
            continue

        plugins.append({
            "name": name,
            "description": definition["description"],
            "version": definition["version"],
            "enabled": enabled,
            "skills": [s.get("name", "") for s in definition.get("skills", [])],
            "mcp_servers": [m.get("name", "") for m in definition.get("mcp_servers", [])],
            "has_hooks": bool(definition.get("hooks")),
        })

    return plugins


def enable(name: str) -> bool:
    """Enable a plugin by name."""
    if name not in _registry:
        return False
    settings = _load_settings()
    settings[name] = True
    _save_settings(settings)
    logger.info("Plugin enabled: %s", name)
    return True


def disable(name: str) -> bool:
    """Disable a plugin by name."""
    if name not in _registry:
        return False
    settings = _load_settings()
    settings[name] = False
    _save_settings(settings)
    logger.info("Plugin disabled: %s", name)
    return True


def is_enabled(name: str) -> bool:
    """Check if a plugin is currently enabled."""
    if name not in _registry:
        return False
    settings = _load_settings()
    user_setting = settings.get(name)
    if user_setting is not None:
        return user_setting
    return _registry[name].get("default_enabled", True)


def get_plugin(name: str) -> dict | None:
    """Get full plugin definition."""
    return _registry.get(name)


def get_enabled_skills() -> list[dict]:
    """Get skills from all enabled plugins."""
    skills = []
    for name, definition in _registry.items():
        if is_enabled(name):
            for skill in definition.get("skills", []):
                skills.append({**skill, "plugin": name})
    return skills


def get_enabled_mcp_servers() -> list[dict]:
    """Get MCP servers from all enabled plugins."""
    servers = []
    for name, definition in _registry.items():
        if is_enabled(name):
            for server in definition.get("mcp_servers", []):
                servers.append({**server, "plugin": name})
    return servers


def get_enabled_hooks() -> dict:
    """Get merged hooks from all enabled plugins."""
    merged: dict = {}
    for name, definition in _registry.items():
        if is_enabled(name):
            for hook_name, hook_config in definition.get("hooks", {}).items():
                if hook_name not in merged:
                    merged[hook_name] = []
                merged[hook_name].append({"plugin": name, "config": hook_config})
    return merged


def reset() -> None:
    """Clear registry and settings (for testing)."""
    global _registry
    _registry = {}
    if PLUGIN_SETTINGS.exists():
        PLUGIN_SETTINGS.unlink()


# --- Settings persistence ---

def _load_settings() -> dict:
    try:
        if PLUGIN_SETTINGS.exists():
            return json.loads(PLUGIN_SETTINGS.read_text())
    except (json.JSONDecodeError, Exception):
        pass
    return {}


def _save_settings(settings: dict) -> None:
    PLUGIN_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    PLUGIN_SETTINGS.write_text(json.dumps(settings, indent=2))
