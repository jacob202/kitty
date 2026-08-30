#!/usr/bin/env python3
"""Compatibility entrypoint — implementation lives in scripts/curation/assign_kb_files.py."""

from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).resolve().parent / "curation" / "assign_kb_files.py"),
        run_name="__main__",
    )
