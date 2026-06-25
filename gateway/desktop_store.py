"""Desktop Phase 1 storage helpers.

Keeps the Quick Capture inbox format stable so desktop and future mobile
surfaces can write into the same append-only queue.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gateway.paths import DESKTOP_LOG_FILE, DESKTOP_PID_DIR, INBOX_FILE


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _normalize_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    return [tag.strip() for tag in tags if isinstance(tag, str) and tag.strip()]


def make_inbox_entry(
    *,
    text: str,
    source: str = "desktop_quick_capture",
    capture_type: str = "text",
    project: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("text is required")
    return {
        "id": str(uuid.uuid4()),
        "created_at": utc_now_iso(),
        "source": source,
        "type": capture_type,
        "text": cleaned,
        "processed": False,
        "project": project,
        "tags": _normalize_tags(tags),
    }


def append_inbox_entry(entry: dict[str, Any], inbox_file: Path = INBOX_FILE) -> dict[str, Any]:
    inbox_file.parent.mkdir(parents=True, exist_ok=True)
    with inbox_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def append_text_capture(
    *,
    text: str,
    source: str = "desktop_quick_capture",
    capture_type: str = "text",
    project: str | None = None,
    tags: list[str] | None = None,
    inbox_file: Path = INBOX_FILE,
) -> dict[str, Any]:
    entry = make_inbox_entry(
        text=text,
        source=source,
        capture_type=capture_type,
        project=project,
        tags=tags,
    )
    return append_inbox_entry(entry, inbox_file=inbox_file)


def read_inbox(limit: int = 20, inbox_file: Path = INBOX_FILE) -> list[dict[str, Any]]:
    if not inbox_file.exists():
        return []
    rows: list[dict[str, Any]] = []
    with inbox_file.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if limit <= 0:
        return rows
    return rows[-limit:]


def count_inbox_entries(inbox_file: Path = INBOX_FILE) -> int:
    if not inbox_file.exists():
        return 0
    with inbox_file.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def tail_log_lines(log_file: Path = DESKTOP_LOG_FILE, limit: int = 50) -> list[str]:
    if not log_file.exists():
        return []
    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    if limit <= 0:
        return lines
    return lines[-limit:]


def runtime_pid_snapshot(pid_dir: Path = DESKTOP_PID_DIR) -> dict[str, int | None]:
    snapshot: dict[str, int | None] = {}
    for name in ("gateway", "ui"):
        pid_file = pid_dir / f"{name}.pid"
        pid: int | None = None
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text(encoding="utf-8").strip())
                os.kill(pid, 0)
            except (ValueError, OSError):
                pid = None
        snapshot[name] = pid
    return snapshot


def desktop_status() -> dict[str, Any]:
    inbox_rows = read_inbox(limit=1)
    latest = inbox_rows[-1] if inbox_rows else None
    pids = runtime_pid_snapshot()
    return {
        "desktop": {
            "inbox_path": str(INBOX_FILE),
            "log_path": str(DESKTOP_LOG_FILE),
            "pid_dir": str(DESKTOP_PID_DIR),
            "quick_capture_source": "desktop_quick_capture",
        },
        "runtime": {
            "gateway_running": pids["gateway"] is not None,
            "gateway_pid": pids["gateway"],
            "ui_running": pids["ui"] is not None,
            "ui_pid": pids["ui"],
        },
        "inbox": {
            "count": count_inbox_entries(),
            "latest_capture_at": latest.get("created_at") if latest else None,
            "latest_source": latest.get("source") if latest else None,
        },
        "recent_logs": tail_log_lines(limit=20),
    }
