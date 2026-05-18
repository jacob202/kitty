#!/usr/bin/env python3
"""
agent-context-brief — prints a compact session brief for agent sessionStart.

Outputs: date, repo path, HOOK_START block from STANDUP.md, last-known state
from SESSION_HANDOFF.md. Kept short intentionally — this runs on every session.
"""
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def extract_block(path: Path, start_marker: str, end_marker: str) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        s = text.find(start_marker)
        e = text.find(end_marker)
        if s == -1 or e == -1:
            return ""
        return text[s + len(start_marker):e].strip()
    except Exception:
        return ""

def first_section(path: Path, heading: str) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        inside = False
        buf = []
        for line in lines:
            if line.strip().startswith("#") and heading.lower() in line.lower():
                inside = True
                buf.append(line)
                continue
            if inside:
                if line.strip().startswith("#") and line.strip() != buf[0].strip():
                    break
                buf.append(line)
        return "\n".join(buf).strip()
    except Exception:
        return ""

print(f"=== Kitty — agent context brief ({date.today()}) ===")
print(f"Repo: {ROOT}\n")

# HOOK_START block from STANDUP.md
hook = extract_block(ROOT / "docs" / "STANDUP.md", "<!-- HOOK_START -->", "<!-- HOOK_END -->")
if hook:
    print(hook)
else:
    print("[STANDUP.md HOOK_START block not found — check docs/STANDUP.md]")

print()

# Quick state from SESSION_HANDOFF.md
handoff = ROOT / "SESSION_HANDOFF.md"
if handoff.exists():
    text = handoff.read_text(encoding="utf-8", errors="ignore")
    # Print just the first 30 lines (compact snapshot)
    snippet = "\n".join(text.splitlines()[:30])
    print("--- Last handoff (SESSION_HANDOFF.md, first 30 lines) ---")
    print(snippet)
    print("...")
else:
    print("[SESSION_HANDOFF.md not found]")
