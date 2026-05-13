"""Emit sessionStart JSON: additional_context = STANDUP compact block (HOOK_START…HOOK_END)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

MARK_START = "<!-- HOOK_START -->"
MARK_END = "<!-- HOOK_END -->"


def main() -> None:
    try:
        sys.stdin.read()
    except Exception:
        pass
    root = Path(__file__).resolve().parents[2]
    standup = root / "docs" / "STANDUP.md"
    if not standup.is_file():
        print(json.dumps({}))
        return
    text = standup.read_text(encoding="utf-8", errors="replace")
    if MARK_START not in text or MARK_END not in text:
        print(json.dumps({}))
        return
    inner = text.split(MARK_START, 1)[1].split(MARK_END, 1)[0].strip()
    print(json.dumps({"additional_context": inner}))


if __name__ == "__main__":
    main()
