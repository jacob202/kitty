"""
Unified reader for project state from canonical control docs.

Source of truth: CURRENT_FOCUS.md and TASKS.md (not stale JSON files)
Used by: brief generation, /phase command, /next command, session start
"""

from pathlib import Path
from typing import Optional


def get_project_root() -> Path:
    """Get the kitty project root."""
    return Path(__file__).resolve().parent.parent.parent  # core/project_state_reader.py -> project root


def read_current_focus(root: Optional[Path] = None) -> dict:
    """Read CURRENT_FOCUS.md and extract key sections.
    
    Returns dict with keys:
        - active_phase: Current phase (e.g. "Phase 4 — Jacob-Only Build")
        - date: Last updated date
        - working_commands: List of working slash commands
        - skills: List of active skills
        - test_status: Current test count
        - progress_items: List of accomplished items today
        - forbidden_work: List of forbidden distractions (scope guards)
    """
    if root is None:
        root = get_project_root()
    
    focus_file = root / "CURRENT_FOCUS.md"
    if not focus_file.exists():
        return {}
    
    try:
        content = focus_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    
    result = {}
    lines = content.splitlines()
    
    # Extract active phase
    for line in lines:
        if line.startswith("## Active Phase"):
            # Next non-empty line after header
            for l in lines[lines.index(line) + 1:]:
                if l.strip() and not l.startswith("#"):
                    result["active_phase"] = l.strip()
                    break
        if line.startswith("Last updated:"):
            result["date"] = line.split(":", 1)[1].strip()
    
    # Extract sections
    for i, line in enumerate(lines):
        if line.startswith("## Working Commands"):
            commands = []
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("#"):
                    break
                if lines[j].startswith("- "):
                    commands.append(lines[j][2:].strip())
            result["working_commands"] = commands
        
        elif line.startswith("## Skills"):
            skills = []
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("#"):
                    break
                if lines[j].startswith("- "):
                    skills.append(lines[j][2:].strip())
            result["skills"] = skills
        
        elif line.startswith("## Today"):
            progress = []
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("#"):
                    break
                if lines[j].startswith("- "):
                    progress.append(lines[j][2:].strip())
            result["progress_items"] = progress
        
        elif line.startswith("## Tests:"):
            result["test_status"] = line.split(":", 1)[1].strip()
        
        elif line.startswith("## Forbidden"):
            forbidden = []
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("#"):
                    break
                if lines[j].startswith("- "):
                    forbidden.append(lines[j][2:].strip())
            result["forbidden_work"] = forbidden
    
    return result


def read_tasks_md(root: Optional[Path] = None) -> dict:
    """Read TASKS.md and extract next action / active tasks.
    
    Returns dict with keys:
        - next_action: Next recommended action
        - open_tasks: List of open/incomplete tasks
        - recent_completed: Recently completed items
    """
    if root is None:
        root = get_project_root()
    
    tasks_file = root / "TASKS.md"
    if not tasks_file.exists():
        return {}
    
    try:
        content = tasks_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    
    result = {
        "next_action": None,
        "open_tasks": [],
        "recent_completed": [],
    }
    
    lines = content.splitlines()
    for i, line in enumerate(lines):
        # Look for "Next Smallest Action" section
        if "Next Smallest Action" in line or "Next Action" in line:
            for j in range(i + 1, min(i + 10, len(lines))):
                if lines[j].startswith("#"):
                    break
                if lines[j].startswith("- ") and not lines[j].startswith("- [x]"):
                    result["next_action"] = lines[j][2:].strip()
                    break
        
        # Look for open tasks (unchecked)
        if lines[i].startswith("- [ ]"):
            result["open_tasks"].append(lines[i][5:].strip())
        
        # Look for recent completed (checked)
        if lines[i].startswith("- [x]"):
            result["recent_completed"].append(lines[i][5:].strip())
    
    return result


def get_current_phase_details(root: Optional[Path] = None) -> str:
    """Get formatted details about current phase."""
    focus = read_current_focus(root)
    phase = focus.get("active_phase", "Unknown")
    return f"**Phase:** {phase}\n**Date:** {focus.get('date', 'Unknown')}"


def format_control_docs_brief(root: Optional[Path] = None) -> str:
    """Format a brief from control docs (used by multiple PM tools)."""
    focus = read_current_focus(root)
    
    lines = [
        "# 🐾 PROJECT STATE",
        "",
        f"**Active:** {focus.get('active_phase', 'Unknown')}",
        f"**Date:** {focus.get('date', 'Unknown')}",
        "",
    ]
    
    # Forbidden work
    forbidden = focus.get("forbidden_work", [])
    if forbidden:
        lines.append("## Scope Guards (Forbidden Work)")
        for item in forbidden:
            lines.append(f"- ❌ {item}")
        lines.append("")
    
    # Progress
    progress = focus.get("progress_items", [])
    if progress:
        lines.append("## Today's Progress")
        for item in progress:
            lines.append(f"- {item}")
        lines.append("")
    
    # Commands
    commands = focus.get("working_commands", [])
    if commands:
        lines.append("## Working Commands")
        for cmd in commands:
            lines.append(f"- {cmd}")
        lines.append("")
    
    # Skills
    skills = focus.get("skills", [])
    if skills:
        lines.append("## Skills")
        for skill in skills:
            lines.append(f"- {skill}")
        lines.append("")
    
    # Tests
    tests = focus.get("test_status", "Unknown")
    lines.append(f"## Tests: {tests}")
    
    return "\n".join(lines)
