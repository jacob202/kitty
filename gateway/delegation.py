"""Delegation packet generator (P3, docs/packets/007).

Turns an approved action into an executor-ready packet file under
docs/packets/. No external calls, no process spawning — the output is a
markdown file and nothing more.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gateway.paths import PACKET_DIR, PACKETS_README

_UNFILLED = "<!-- EXECUTOR: unfilled — packet author must complete -->"

_SLOTS = [
    "title",
    "executor_type",
    "purpose",
    "scope",
    "files_touched",
    "files_not_to_touch",
    "steps",
    "acceptance",
    "verification_commands",
    "risks",
    "too_broad_if",
    "jacob_reviews",
]

_TEMPLATE = """# Packet {number} — {title}

- **Status:** draft (generated {date} from action {action_id})
- **Best executor:** {executor_type}
- **Purpose:** {purpose}

## Exact scope

{scope}

## Files likely touched

{files_touched}

## Files not to touch

{files_not_to_touch}

## Steps

{steps}

## Acceptance criteria

{acceptance}

## Verification

```bash
{verification_commands}
```

## Risks / rollback

{risks}

## Too broad if

{too_broad_if}

## Jacob reviews

{jacob_reviews}
"""


def render_packet(action: dict[str, Any]) -> str:
    """Render a packet from an action payload. Pure function, no side effects."""
    payload = action.get("payload") or {}
    number = action.get("packet_number") or next_packet_number()
    values: dict[str, str] = {
        "number": str(number),
        "date": _today(),
        "action_id": str(action.get("id", "")),
    }
    for slot in _SLOTS:
        value = payload.get(slot)
        values[slot] = _render_value(value)
    return _TEMPLATE.format(**values)


def next_packet_number() -> int:
    """Return max packet number + 1 found in docs/packets/*.md filenames."""
    max_num = 0
    if PACKET_DIR.exists():
        for path in PACKET_DIR.glob("*.md"):
            match = re.match(r"^(\d{3})-", path.name)
            if match:
                max_num = max(max_num, int(match.group(1)))
    return max_num + 1


def write_packet(action: dict[str, Any]) -> Path:
    """Render and write a packet file; update the registry."""
    payload = action.get("payload") or {}
    title = str(payload.get("title") or action.get("title") or "untitled").strip()
    number = action.get("packet_number") or next_packet_number()
    slug = _slug(title)
    path = PACKET_DIR / f"{number:03d}-{slug}.md"

    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing packet: {path}")

    action_with_number = {**action, "packet_number": number}
    text = render_packet(action_with_number)
    path.write_text(text, encoding="utf-8")

    _append_registry_row(number=number, title=title)
    return path


def _render_value(value: Any) -> str:
    if value is None:
        return _UNFILLED
    if isinstance(value, str):
        text = value.strip()
        return text if text else _UNFILLED
    if isinstance(value, list):
        if not value:
            return _UNFILLED
        items = "\n".join(f"- {_render_value(v)}" for v in value if v is not None)
        return items if items.strip() else _UNFILLED
    return str(value).strip() or _UNFILLED


def _slug(title: str) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in title]
    slug = "".join(keep).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug[:60] or "packet"


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _append_registry_row(*, number: int, title: str) -> None:
    """Append a row to the packets README registry table."""
    if not PACKETS_README.exists():
        raise FileNotFoundError(f"packets README not found: {PACKETS_README}")

    text = PACKETS_README.read_text(encoding="utf-8")
    table_lines = text.splitlines()

    # Locate the table body: lines starting with "|" that contain the registry.
    table_start = None
    for i, line in enumerate(table_lines):
        if line.startswith("| #") and "Packet" in line:
            table_start = i
            break
    if table_start is None:
        raise ValueError(f"could not parse registry table in {PACKETS_README}")

    # Find the end of the table (next blank line or non-table line).
    table_end = len(table_lines)
    for i in range(table_start + 1, len(table_lines)):
        if not table_lines[i].strip().startswith("|"):
            table_end = i
            break

    row = f"| {number:03d} | {title} | (generated) | ✏️ draft (generated) |"
    new_lines = table_lines[:table_end] + [row] + table_lines[table_end:]
    PACKETS_README.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    import sys

    from gateway import action_queue

    if len(sys.argv) < 2:
        print("Usage: python -m gateway.delegation <action-id>", file=sys.stderr)
        sys.exit(1)

    action_id = int(sys.argv[1])
    action = action_queue.execute(action_id)
    print(action.get("result", ""))
