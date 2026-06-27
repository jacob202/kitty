#!/usr/bin/env python3
"""Append a durable preference to config/PREFERENCES.md.

Used by the /remember skill. Preferences take effect immediately and are
read back at the start of every session by recall-thread.sh.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREFS = ROOT / "config" / "PREFERENCES.md"


def main(argv: list[str]) -> int:
    text = " ".join(argv).strip()
    if not text:
        print("Nothing to remember: give me the preference text.", file=sys.stderr)
        return 2

    if not PREFS.exists():
        print(f"Missing {PREFS} — run from the kitty repo root.", file=sys.stderr)
        return 1

    line = f"- ({date.today().isoformat()}) {text}\n"
    with PREFS.open("a", encoding="utf-8") as f:
        f.write(line)

    print(f"Remembered: {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
