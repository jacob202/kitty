"""Task Boundary System — Antigravity-style task tracking and progress reporting.

This module implements structured task boundaries that group agent actions into
named tasks with progress summaries, similar to Antigravity's task_boundary tool.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.task_boundary")

KITTY_DIR = DATA_DIR

VALID_STATUSES = ("planning", "in_progress", "reviewing", "completed", "blocked")


class TaskBoundary:
    """Simulate Antigravity's task_boundary tool — groups agent actions into named tasks."""

    def __init__(self):
        self.log_file = KITTY_DIR / "task_boundaries.jsonl"
        self.active_tasks: Dict[str, dict] = {}
        self._load()

    def _load(self):
        """Load existing task boundaries from disk."""
        if self.log_file.exists():
            with open(self.log_file) as f:
                for line in f:
                    entry = json.loads(line.strip())
                    self.active_tasks[entry["task_id"]] = entry

    def _append(self, entry: dict):
        """Append entry to log file and update cache."""
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        self.active_tasks[entry["task_id"]] = entry

    def open(self, task_id: str, name: str, description: str = "") -> dict:
        """Declare a new high-level task boundary."""
        entry = {
            "task_id": task_id,
            "name": name,
            "description": description,
            "status": "planning",
            "progress_summary": "",
            "opened_at": datetime.now().isoformat(),
            "updates": [],
        }
        self._append(entry)
        logger.info("Task boundary opened: %s", name)
        return entry

    def update(self, task_id: str, status: str, summary: str = ""):
        """Update task progress — like task_boundary update."""
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}. Valid: {VALID_STATUSES}")

        entry = self.active_tasks.get(task_id, {})
        if not entry:
            raise ValueError(f"Task not found: {task_id}")

        entry["status"] = status
        entry["progress_summary"] = summary
        entry["updates"].append(
            {
                "timestamp": datetime.now().isoformat(),
                "status": status,
                "summary": summary,
            }
        )
        self._append(entry)
        logger.info("Task %s updated to %s", task_id, status)

    def close(self, task_id: str, final_summary: str = "", success: bool = True):
        """Mark task completed or failed."""
        entry = self.active_tasks.get(task_id, {})
        if not entry:
            raise ValueError(f"Task not found: {task_id}")

        entry["status"] = "completed" if success else "blocked"
        entry["progress_summary"] = final_summary
        entry["closed_at"] = datetime.now().isoformat()
        entry["updates"].append(
            {
                "timestamp": datetime.now().isoformat(),
                "status": entry["status"],
                "summary": final_summary,
            }
        )
        self._append(entry)
        logger.info("Task %s closed: %s", task_id, "success" if success else "blocked")

    def current_summary(self) -> str:
        """Return a human-readable summary of all active boundaries."""
        lines = ["=== Task Boundaries ==="]
        for tid, t in self.active_tasks.items():
            icon = {
                "planning": "📋",
                "in_progress": "⚡",
                "reviewing": "👀",
                "completed": "✅",
                "blocked": "❌",
            }.get(t["status"], "❓")
            lines.append(f" {icon} [{tid}] {t['name']} — {t['status']}")
            if t.get("progress_summary"):
                lines.append(f"   {t['progress_summary'][:100]}")
        return "\n".join(lines)

    def get(self, task_id: str) -> Optional[dict]:
        """Get task details by ID."""
        return self.active_tasks.get(task_id)

    def list_all(self) -> List[dict]:
        """List all task boundaries."""
        return list(self.active_tasks.values())


# Global instance
task_boundary = TaskBoundary()
