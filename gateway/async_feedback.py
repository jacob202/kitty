"""Async Feedback Loop — Antigravity-style notifications and user feedback.

This module implements asynchronous feedback where agents post notifications
and users can comment on artifacts without interrupting the agent loop.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.async_feedback")

KITTY_DIR = DATA_DIR


class AsyncFeedback:
    """Async feedback loop — agent posts notifications, user comments on artifacts."""

    def __init__(self):
        self.notify_file = KITTY_DIR / "notifications.jsonl"
        self.feedback_dir = KITTY_DIR / "feedback"
        self.feedback_dir.mkdir(exist_ok=True)

    def notify(self, message: str, artifact_path: str = "", priority: str = "info"):
        """Agent calls this to notify user — like notify_user tool."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "artifact": artifact_path,
            "priority": priority,
            "acknowledged": False,
        }
        with open(self.notify_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        
        # Terminal notification
        print(f"\a🔔 Kitty: {message}")
        logger.info(f"Notification: {message}")

    def check_feedback(self, artifact_path: str) -> List[str]:
        """Agent polls this to check for user comments on an artifact."""
        feedback_file = self.feedback_dir / f"{Path(artifact_path).stem}_feedback.jsonl"
        if not feedback_file.exists():
            return []
        
        comments = []
        with open(feedback_file) as f:
            for line in f:
                entry = json.loads(line.strip())
                comments.append(entry.get("comment", ""))
        return comments

    def add_feedback(self, artifact_path: str, comment: str):
        """User adds feedback on an artifact — like Google Docs comments."""
        feedback_file = self.feedback_dir / f"{Path(artifact_path).stem}_feedback.jsonl"
        entry = {
            "timestamp": datetime.now().isoformat(),
            "artifact": artifact_path,
            "comment": comment,
        }
        with open(feedback_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        logger.info(f"Feedback saved for {artifact_path}: {comment[:50]}...")
        print(f"✅ Feedback saved for {artifact_path}")

    def get_notifications(self, limit: int = 20) -> List[dict]:
        """Get recent notifications."""
        if not self.notify_file.exists():
            return []
        
        notifications = []
        with open(self.notify_file) as f:
            for line in f:
                entry = json.loads(line.strip())
                notifications.append(entry)
        
        return notifications[-limit:]

    def mark_acknowledged(self, artifact_path: str):
        """Mark all notifications for an artifact as acknowledged."""
        if not self.notify_file.exists():
            return
        
        entries = []
        with open(self.notify_file) as f:
            for line in f:
                entry = json.loads(line.strip())
                if entry.get("artifact") == artifact_path:
                    entry["acknowledged"] = True
                entries.append(entry)
        
        with open(self.notify_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")


# Global instance
async_feedback = AsyncFeedback()
