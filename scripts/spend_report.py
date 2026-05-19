#!/usr/bin/env python3
"""Compatibility entrypoint — implementation lives in scripts/ops/spend_report.py."""

from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).resolve().parent / "ops" / "spend_report.py"),
        run_name="__main__",
    )
