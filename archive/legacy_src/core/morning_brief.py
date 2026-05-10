"""
Deterministic morning brief generator — no LLM dependency.
"""
import os
import re
from datetime import datetime
from pathlib import Path

def _read_file(name: str, root: str = None) -> str:
    """Read a file from project root, return '' if missing."""
    if root is None:
        root = Path(__file__).resolve().parent.parent.parent
    else:
        root = Path(root)
    try:
        return (root / name).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""

def _extract_section(md: str, header: str) -> str:
    """Extract text under a markdown header until next ## or end."""
    lines = md.splitlines()
    capture = False
    result = []
    wanted = _normalize_heading(header)
    for line in lines:
        if line.lstrip().startswith("#"):
            if capture:
                break
            if wanted and wanted in _normalize_heading(line):
                capture = True
                continue
        elif capture:
            result.append(line)
    return "\n".join(result).strip()

def _normalize_heading(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()

def _first_content_line(section: str) -> str:
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- ["):
            return _clean_inline(re.sub(r"^-\s*\[[ xX]?\]\s*", "", stripped))
        if re.match(r"^\d+\.\s+", stripped):
            return _clean_inline(re.sub(r"^\d+\.\s+", "", stripped))
        if stripped.startswith("- "):
            return _clean_inline(stripped[2:])
        return _clean_inline(stripped)
    return ""

def _clean_inline(text: str) -> str:
    return re.sub(r"[*_`]+", "", text).strip()

def _get_active_focus(root: str = None) -> str:
    md = _read_file("CURRENT_FOCUS.md", root)
    if not md:
        return "unknown"
    for line in md.splitlines():
        if line.startswith("Active phase:"):
            return line.split(":", 1)[-1].strip()
        if line.startswith("Current task:"):
            return line.split(":", 1)[-1].strip()
    current_task = _first_content_line(_extract_section(md, "Current Task"))
    if current_task:
        return current_task
    active_phase = _first_content_line(_extract_section(md, "Active Phase"))
    if active_phase:
        return active_phase
    return "unknown"

def _get_last_completed(root: str = None) -> str:
    md = _read_file("SESSION_SUMMARY.md", root)
    if not md:
        return "nothing yet"
    for line in md.splitlines():
        if "Last completed:" in line:
            return line.split(":", 1)[-1].strip()
    return "nothing yet"

def _get_next_action(root: str = None) -> str:
    md = _read_file("TASKS.md", root)
    if not md:
        return "review CURRENT_FOCUS.md"
    next_smallest = _first_content_line(_extract_section(md, "Next Smallest Action"))
    if next_smallest:
        return next_smallest
    active = _first_content_line(_extract_section(md, "Active"))
    if active:
        return active
    in_open = False
    for line in md.splitlines():
        if line.startswith("## Open"):
            in_open = True
            continue
        if line.startswith("## "):
            in_open = False
        if in_open and line.startswith("- ["):
            return line.lstrip("- [] ").strip()
    return "no open tasks — check CURRENT_FOCUS.md"

def _get_forbidden(root: str = None) -> list:
    md = _read_file("CURRENT_FOCUS.md", root)
    if not md:
        return []
    section = _extract_section(md, "Forbidden Work")
    if not section:
        return []
    return [l.strip("- ").strip() for l in section.splitlines() if l.strip().startswith("-")]

def generate_brief(root: str = None) -> dict:
    """Generate deterministic morning brief."""
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "active_focus": _get_active_focus(root),
        "last_completed": _get_last_completed(root),
        "next_action": _get_next_action(root),
        "forbidden_distractions": _get_forbidden(root),
    }

def brief_to_text(brief: dict) -> str:
    """Format brief dict as plain text."""
    lines = [
        f"Today: {brief['date']}",
        f"Active focus: {brief['active_focus']}",
        f"Last completed: {brief['last_completed']}",
        f"Next concrete action: {brief['next_action']}",
    ]
    if brief["forbidden_distractions"]:
        lines.append("Do not:")
        for item in brief["forbidden_distractions"]:
            lines.append(f"- {item}")
    return "\n".join(lines)
