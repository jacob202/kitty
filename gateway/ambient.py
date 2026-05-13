"""Ambient Context Awareness — detect what Jacob is doing and preload context.

Uses macOS-specific AppleScript to detect active application, then matches
against domain config for auto-mode switching and context preloading.

All local-only, fully opt-in. Requires KITTY_AMBIENT_ENABLED=1.

Public API:
  get_active_app() -> str | None      Currently focused application name
  suggest_domain() -> str | None      Suggest domain based on active app
  preload_context() -> dict           Context to preload based on activity
"""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger("kitty.ambient")

APP_DOMAIN_MAP: dict[str, str] = {
    "safari": "research",
    "chrome": "research",
    "firefox": "research",
    "brave": "research",
    "terminal": "code",
    "warp": "code",
    "iterm": "code",
    "cursor": "code",
    "vscode": "code",
    "xcode": "code",
    "preview": "repair",  # often viewing schematics/PDFs
    "photos": "soul",
    "messages": "soul",
    "music": "soul",
    "health": "health",
    "fitness": "health",
    "calendar": "soul",
}


def is_enabled() -> bool:
    return os.environ.get("KITTY_AMBIENT_ENABLED", "").strip().lower() in ("1", "true", "yes")


def get_active_app() -> Optional[str]:
    """Get the name of the currently active macOS application."""
    if not is_enabled():
        return None
    try:
        result = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get name of first application process whose frontmost is true'],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip().lower()
    except Exception as e:
        logger.debug("Ambient app detection failed: %s", e)
    return None


def suggest_domain() -> Optional[str]:
    """Suggest a domain based on the active application."""
    app = get_active_app()
    if not app:
        return None
    return APP_DOMAIN_MAP.get(app)


def preload_context() -> dict:
    """Return context hints based on current activity."""
    app = get_active_app()
    domain = suggest_domain()

    result = {"active_app": app, "suggested_domain": domain}

    if domain == "repair":
        result["preload_hint"] = "service_manual"
    elif domain == "code":
        result["preload_hint"] = "code_context"
    elif domain == "health":
        result["preload_hint"] = "health_data"
    elif domain == "research":
        result["preload_hint"] = "research_topic"

    return result


def get_ambient_text() -> str:
    """Return a brief ambient context string for system prompt injection."""
    if not is_enabled():
        return ""

    app = get_active_app()
    domain = suggest_domain()

    if not app:
        return ""

    lines = [f"[AMBIENT: Jacob is in {app}"]

    # Try to get current URL/file
    try:
        if app in ("safari", "chrome", "brave"):
            result = subprocess.run(
                ["osascript", "-e",
                 f'tell application "{app.title()}" to get URL of active tab of front window'],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0 and result.stdout.strip():
                lines.append(f" — viewing {result.stdout.strip()[:100]}")
        elif app in ("cursor", "vscode"):
            result = subprocess.run(
                ["osascript", "-e",
                 f'tell application "{app.title()}" to get name of front window'],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0:
                lines.append(f" — {result.stdout.strip()[:100]}")
    except Exception:
        pass

    lines.append("]")
    return "".join(lines)
