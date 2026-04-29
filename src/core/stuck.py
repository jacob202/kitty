import re
from pathlib import Path
from typing import Dict, List, Union

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""

def _section(text: str, heading: str) -> str:
    wanted = re.sub(r"[^a-z0-9]+", " ", heading.lower()).strip()
    capture = False
    lines: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            if capture:
                break
            current = re.sub(r"[^a-z0-9]+", " ", line.lower()).strip()
            if wanted and wanted in current:
                capture = True
            continue
        if capture:
            lines.append(line)
    return "\n".join(lines).strip()

def _first_action(text: str) -> str | None:
    for line in text.splitlines():
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
    return None

def _clean_inline(text: str) -> str:
    return re.sub(r"[*_`]+", "", text).strip()

def get_stuck_action(root: str | Path | None = None) -> Dict[str, Union[str, List[str]]]:
    project_root = Path(root).resolve() if root else PROJECT_ROOT
    current_focus_path = project_root / "CURRENT_FOCUS.md"
    tasks_path = project_root / "TASKS.md"
    default_response = {
        "current_focus": "No CURRENT_FOCUS.md found — create one to define active task",
        "next_action": "Create CURRENT_FOCUS.md with Current task, Forbidden work, and next steps",
        "do_not": [],
        "report_back": "still stuck: missing CURRENT_FOCUS.md"
    }

    if not current_focus_path.exists():
        return default_response

    focus_content = _read(current_focus_path)

    current_focus_match = re.search(
        r'^(Current task|Active task):\s*(.*)$',
        focus_content,
        re.MULTILINE
    )
    current_focus = current_focus_match.group(2).strip() if current_focus_match else None
    if not current_focus:
        current_focus = _first_action(_section(focus_content, "Current Task"))
    if not current_focus:
        current_focus = _first_action(_section(focus_content, "Active Phase"))
    if not current_focus:
        current_focus = "No active task defined in CURRENT_FOCUS.md"

    do_not: List[str] = []
    forbidden_match = re.search(
        r'#+\s*Forbidden work\s*\n(.*?)(?=\n#+|$)',
        focus_content,
        re.DOTALL | re.IGNORECASE
    )
    if forbidden_match:
        forbidden_lines = forbidden_match.group(1).strip().split('\n')
        for line in forbidden_lines:
            line = line.strip()
            if line.startswith('-'):
                do_not.append(line.lstrip('- ').strip())

    next_action = None
    next_action_match = re.search(
        r'^Next action:\s*(.*)$',
        focus_content,
        re.MULTILINE
    )
    if next_action_match:
        next_action = next_action_match.group(1).strip()
    else:
        if tasks_path.exists():
            tasks_content = _read(tasks_path)
            next_action = _first_action(_section(tasks_content, "Next Smallest Action"))
        if not next_action and tasks_path.exists():
            pending_task_match = re.search(
                r'-\s*\[\s*\]\s*(.*)$',
                tasks_content,
                re.MULTILINE
            )
            if pending_task_match:
                next_action = pending_task_match.group(1).strip()

    if not next_action:
        next_action = "Define next concrete action in CURRENT_FOCUS.md or TASKS.md"

    forbidden_phrases = ["research", "redesign", "open a new tool", "change architecture"]
    next_action_lower = next_action.lower()
    for phrase in forbidden_phrases:
        if phrase in next_action_lower:
            next_action = "Complete a small, concrete task from TASKS.md"
            break

    if len(next_action) > 200:
        next_action = next_action[:197] + "..."

    report_back = f"done {next_action}" if next_action else "still stuck: no actionable task found"

    return {
        "current_focus": current_focus,
        "next_action": next_action,
        "do_not": do_not,
        "report_back": report_back
    }
