#!/usr/bin/env python3
"""
Kitty Config Loader - Auto-loads WORKING_GUIDELINES.md and SOUL.md on import.
Installs as import hook. No explicit import needed in CLIs.
"""

import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent
CONFIG_DIR = PROJECT_ROOT / "config"

WORKING_GUIDELINES_PATH = CONFIG_DIR / "WORKING_GUIDELINES.md"
SOUL_PATH = CONFIG_DIR / "SOUL.md"
CONFIG_JSON_PATH = CONFIG_DIR / "config.json"

_loaded: bool = False
_working_guidelines: str = ""
_soul: str = ""
_config: dict[str, Any] = {}


def load_config() -> dict[str, Any]:
    """Load all config files."""
    global _loaded, _working_guidelines, _soul, _config

    if _loaded:
        return {"guidelines": _working_guidelines, "soul": _soul, "json": _config}

    if WORKING_GUIDELINES_PATH.exists():
        _working_guidelines = WORKING_GUIDELINES_PATH.read_text()

    if SOUL_PATH.exists():
        _soul = SOUL_PATH.read_text()

    import json
    if CONFIG_JSON_PATH.exists():
        try:
            _config = json.loads(CONFIG_JSON_PATH.read_text())
        except json.JSONDecodeError:
            _config = {}

    _loaded = True
    os.environ["KITTY_PROJECT_ROOT"] = str(PROJECT_ROOT)
    os.environ["KITTY_GUIDELINES_LOADED"] = "1"

    return {"guidelines": _working_guidelines, "soul": _soul, "json": _config}


class KittyConfigFinder:
    """Meta path finder that loads config on first import."""

    def find_module(self, name: str, path: str | None = None):
        if not _loaded and name and not name.startswith("_"):
            load_config()
        return None

    def find_spec(self, name: str, path: str | None = None, target=None):
        if not _loaded and name and not name.startswith("_"):
            load_config()
        return None


def install():
    """Install auto-loader. Call once at startup."""
    if _loaded:
        return

    load_config()

    # Insert as first meta_path finder
    finder = KittyConfigFinder()
    sys.meta_path.insert(0, finder)


# Auto-install on module load
install()


# Convenience accessors
def get_working_guidelines() -> str:
    return _working_guidelines

def get_soul() -> str:
    return _soul

def get_config(key: str, default: Any = None) -> Any:
    return _config.get(key, default)
