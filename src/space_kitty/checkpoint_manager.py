"""
Checkpoint management for context cutoff resilience.
Saves conversation history + active job IDs + mood signals.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.session_memory import SessionMemory


class CheckpointManager:
    """Save and restore checkpoints for context recovery."""

    def __init__(self):
        self.session_memory = SessionMemory()
        self.checkpoint_dir = Path("data/checkpoints")
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(
        self,
        history: list[dict[str, str]],
        active_jobs: list[int],
        mood: str = "focused"
    ) -> str:
        """Save checkpoint with history + active jobs + mood."""
        checkpoint = {
            "timestamp": datetime.now().isoformat(),
            "history": history,
            "active_jobs": active_jobs,
            "mood": mood,
            "history_size": len(history),
            "job_count": len(active_jobs),
        }

        session_id = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Save to session_memory
        returned_id = self.session_memory.save_session(
            session_id=session_id,
            state=checkpoint,
            metadata={
                "checkpoint_type": "context_recovery",
                "history_size": len(history),
                "job_count": len(active_jobs),
            }
        )

        return returned_id

    def load_checkpoint(self, checkpoint_id: str) -> dict[str, Any] | None:
        """Load checkpoint by ID."""
        try:
            return self.session_memory.load_session(checkpoint_id)
        except Exception:
            return None

    def list_checkpoints(self) -> list[dict[str, str]]:
        """List all available checkpoints."""
        sessions = self.session_memory.list_sessions()
        return [
            {
                "id": s.get("session_id"),
                "saved_at": s.get("saved_at"),
                "metadata": s.get("metadata"),
            }
            for s in sessions
        ]

    def get_last_checkpoint(self) -> dict[str, Any] | None:
        """Get most recent checkpoint."""
        checkpoints = self.list_checkpoints()
        if not checkpoints:
            return None
        latest = sorted(checkpoints, key=lambda x: x.get("saved_at", ""))[-1]
        return self.load_checkpoint(latest["id"])

    def save_mood(self, mood: str):
        """Save current mood signal."""
        mood_log = self.checkpoint_dir / "moods.jsonl"
        with open(mood_log, "a") as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "mood": mood,
            }) + "\n")

    def get_last_mood(self) -> str | None:
        """Get last recorded mood."""
        mood_log = self.checkpoint_dir / "moods.jsonl"
        if not mood_log.exists():
            return None
        with open(mood_log) as f:
            lines = f.readlines()
        if lines:
            return json.loads(lines[-1]).get("mood")
        return None

    def cleanup_old_checkpoints(self, keep: int = 5):
        """Keep only last N checkpoints."""
        checkpoints = self.list_checkpoints()
        if len(checkpoints) > keep:
            to_delete = checkpoints[:-keep]
            for cp in to_delete:
                self.session_memory.delete_session(cp["id"])
