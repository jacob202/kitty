"""Compatibility shim for the canonical local journal memory database."""

from __future__ import annotations

import importlib.util
from pathlib import Path

try:
    from src.memory.journal_db import JournalDB, PKAMemoryDB
except ImportError:
    import importlib.util
    from pathlib import Path
    _MODULE_PATH = Path(__file__).parent / "src" / "memory" / "journal_db.py"
    if not _MODULE_PATH.exists():
         _MODULE_PATH = Path(__file__).parent / "scripts" / "journal_db.py"

    _SPEC = importlib.util.spec_from_file_location("_kitty_internal_journal_db", _MODULE_PATH)
    if _SPEC is None or _SPEC.loader is None:
        raise ImportError(f"Could not load journal DB module from {_MODULE_PATH}")
    _module = importlib.util.module_from_spec(_SPEC)
    _SPEC.loader.exec_module(_module)
    PKAMemoryDB = _module.PKAMemoryDB
    JournalDB = _module.JournalDB

__all__ = ["PKAMemoryDB", "JournalDB"]
