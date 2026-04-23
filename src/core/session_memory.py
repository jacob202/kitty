#!/usr/bin/env python3
"""
Session Memory Persistence for Kitty Agents
Allows agents to save/restore state across sessions
"""

import json
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

_SAFE_SESSION_RE = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")


class SessionMemory:
    """Save and restore agent session state"""

    def __init__(self, session_dir: str = "data/sessions"):
        self.session_dir = Path(session_dir).resolve()
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def _validate_session_id(self, session_id: str) -> str:
        """Validate session ID to prevent path traversal attacks."""
        if not session_id or not isinstance(session_id, str):
            raise ValueError(f"Invalid session ID: {session_id!r}")
        if not _SAFE_SESSION_RE.match(session_id):
            raise ValueError(f"Invalid session ID: {session_id!r}")
        # Additional path traversal protection - ensure resolves within session_dir
        session_file = self.session_dir / f"{session_id}.json"
        try:
            resolved = session_file.resolve()
            # Verify resolved path is within session_dir
            resolved.relative_to(self.session_dir)
            return session_id
        except ValueError:
            raise ValueError(f"Session ID path traversal attempt: {session_id!r}")

    def save_session(
        self, session_id: str, state: dict[str, Any], metadata: dict | None = None
    ) -> str:
        """Save agent session state"""
        if session_id is None:
            session_id = str(uuid4())[:8]
        session_id = self._validate_session_id(session_id)

        session_file = self.session_dir / f"{session_id}.json"

        data = {
            "session_id": session_id,
            "saved_at": datetime.now().isoformat(),
            "state": state,
            "metadata": metadata or {},
        }

        with open(session_file, "w") as f:
            json.dump(data, f, indent=2)

        return session_id

    def load_session(self, session_id: str) -> dict | None:
        """Load agent session state"""
        session_id = self._validate_session_id(session_id)
        session_file = self.session_dir / f"{session_id}.json"

        if not session_file.exists():
            return None

        with open(session_file) as f:
            return json.load(f)

    def list_sessions(self) -> list[dict]:
        """List all saved sessions"""
        sessions = []

        for session_file in self.session_dir.glob("*.json"):
            try:
                with open(session_file) as f:
                    data = json.load(f)
                    sessions.append(
                        {
                            "session_id": data.get("session_id"),
                            "saved_at": data.get("saved_at"),
                            "metadata": data.get("metadata", {}),
                        }
                    )
            except Exception:
                pass

        return sorted(sessions, key=lambda x: x.get("saved_at", ""), reverse=True)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        session_id = self._validate_session_id(session_id)
        session_file = self.session_dir / f"{session_id}.json"

        if session_file.exists():
            session_file.unlink()
            return True
        return False


# Global instance (thread-safe)
_session_memory = None
_session_memory_lock = threading.Lock()


def get_session_memory() -> SessionMemory:
    """Get global session memory instance (thread-safe)"""
    global _session_memory
    if _session_memory is None:
        with _session_memory_lock:
            if _session_memory is None:
                _session_memory = SessionMemory()
    return _session_memory


def save_agent_state(
    session_id: str, agent_name: str, state: dict[str, Any], metadata: dict | None = None
) -> str:
    """Save agent state to session memory"""
    memory = get_session_memory()
    return memory.save_session(session_id, {"agent": agent_name, "state": state}, metadata)


def load_agent_state(session_id: str) -> dict | None:
    """Load agent state from session memory"""
    memory = get_session_memory()
    return memory.load_session(session_id)


# CLI commands for session management
def main():
    """Session memory CLI"""
    import typer

    app = typer.Typer(help="Session Memory Management")

    @app.command("save")
    def save(
        session_id: str = typer.Argument(..., help="Session ID"),
        state_file: str = typer.Option(None, "--file", "-f", help="JSON file with state"),
    ):
        """Save a session"""
        memory = get_session_memory()

        if state_file:
            with open(state_file) as f:
                state = json.load(f)
        else:
            state = {"note": "manual save"}

        sid = memory.save_session(session_id, state)
        typer.echo(f"Saved session: {sid}")

    @app.command("load")
    def load(
        session_id: str = typer.Argument(..., help="Session ID"),
    ):
        """Load a session"""
        memory = get_session_memory()
        data = memory.load_session(session_id)

        if data:
            typer.echo(json.dumps(data, indent=2))
        else:
            typer.echo(f"Session {session_id} not found")
            raise typer.Exit(1)

    @app.command("list")
    def list_sessions():
        """List all sessions"""
        memory = get_session_memory()
        sessions = memory.list_sessions()

        for s in sessions:
            typer.echo(f"{s['session_id']} - {s.get('saved_at', 'unknown')}")

    @app.command("delete")
    def delete(
        session_id: str = typer.Argument(..., help="Session ID"),
    ):
        """Delete a session"""
        memory = get_session_memory()
        if memory.delete_session(session_id):
            typer.echo(f"Deleted session: {session_id}")
        else:
            typer.echo(f"Session {session_id} not found")
            raise typer.Exit(1)

    app()


if __name__ == "__main__":
    main()
