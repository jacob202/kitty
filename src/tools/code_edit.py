"""
code_edit — safe self-modification tool for kitty.
Always backs up before writing. Validates syntax before committing.
Only operates on files within the AgentCompany directory.
"""
import ast
import json
import shutil
from datetime import datetime
from pathlib import Path

KITTY_ROOT   = Path(__file__).parent.parent.resolve()
BACKUP_DIR   = Path.home() / "Documents/Kitty/backups"
CORE_FILES   = {"supervisor.py", "cli.py"}   # require extra confirmation


def _backup(path: Path) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"{path.name}.{ts}.bak"
    shutil.copy2(path, dest)
    return dest


def _validate(path: Path, content: str) -> str | None:
    """Return error string if invalid, None if OK."""
    if path.suffix == ".py":
        try:
            ast.parse(content)
        except SyntaxError as e:
            return f"Python syntax error: {e}"
    elif path.suffix == ".json":
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            return f"JSON parse error: {e}"
    return None


def read_kitty_file(rel_path: str) -> str:
    """Read a file relative to the kitty root. Returns content or error."""
    path = (KITTY_ROOT / rel_path).resolve()
    if not str(path).startswith(str(KITTY_ROOT)):
        return "Error: path outside kitty directory"
    if not path.exists():
        return f"Error: {rel_path} not found"
    return path.read_text()


def write_kitty_file(rel_path: str, content: str, confirmed: bool = False) -> str:
    """
    Write content to a kitty file safely.
    - Backs up existing file first
    - Validates syntax (Python/JSON)
    - Core files (supervisor.py, cli.py) require confirmed=True
    Returns status string.
    """
    path = (KITTY_ROOT / rel_path).resolve()
    if not str(path).startswith(str(KITTY_ROOT)):
        return "Error: path outside kitty directory — write refused"

    if path.name in CORE_FILES and not confirmed:
        return (
            f"CONFIRM_REQUIRED: {rel_path} is a core file. "
            "Re-call with confirmed=true after reviewing the proposed change."
        )

    err = _validate(path, content)
    if err:
        return f"Validation failed — file NOT written. {err}"

    backup_path = None
    if path.exists():
        backup_path = _backup(path)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

    backup_note = f" (backup: {backup_path.name})" if backup_path else ""
    return f"OK: wrote {rel_path}{backup_note}"


def list_kitty_files(subdir: str = "") -> str:
    """List files in kitty directory or a subdirectory."""
    target = (KITTY_ROOT / subdir).resolve()
    if not str(target).startswith(str(KITTY_ROOT)):
        return "Error: path outside kitty directory"
    if not target.exists():
        return f"Error: {subdir} not found"
    lines = []
    for p in sorted(target.rglob("*")):
        if p.is_file() and "__pycache__" not in str(p) and "venv" not in str(p):
            lines.append(str(p.relative_to(KITTY_ROOT)))
    return "\n".join(lines) or "(empty)"


def patch_agent_json(agent_name: str, field: str, operation: str, value) -> str:
    """
    Patch a specific field in an agent JSON without rewriting the whole file.
    operation: 'set' | 'append' | 'remove'
    field: 'keywords' | 'system_prompt' | 'model' | 'tools' | 'role'
    """
    rel = f"agents/{agent_name}.json"
    path = KITTY_ROOT / rel
    if not path.exists():
        agents = [f.stem for f in (KITTY_ROOT / "agents").glob("*.json")]
        return f"Agent '{agent_name}' not found. Available: {agents}"

    data = json.loads(path.read_text())
    current = data.get(field)

    if operation == "set":
        data[field] = value
    elif operation == "append":
        if isinstance(current, list):
            if value not in current:
                current.append(value)
                data[field] = current
            else:
                return f"'{value}' already in {field}"
        elif isinstance(current, str):
            data[field] = current + "\n" + value
        else:
            data[field] = value
    elif operation == "remove":
        if isinstance(current, list) and value in current:
            current.remove(value)
            data[field] = current
        else:
            return f"'{value}' not found in {field}"
    else:
        return f"Unknown operation: {operation}. Use set/append/remove"

    new_content = json.dumps(data, indent=2)
    return write_kitty_file(rel, new_content)
