"""
MCP Tmux Integration - Spawn agents in tmux panes for fire-and-forget execution.
This module provides MCP tools for Kitty to dispatch agents via tmux.
"""

import shlex
import subprocess
from pathlib import Path

from src.core.aura_loader import get_branding

_branding = get_branding()
_DEFAULT_SESSION = _branding["session_prefix"]


def _tmux_command(cmd: list[str]) -> tuple[bool, str]:
    """Execute a tmux command. Returns (success, output_or_error)."""
    try:
        result = subprocess.run(["tmux"] + cmd, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip()
    except FileNotFoundError:
        return False, "tmux not installed"
    except subprocess.TimeoutExpired:
        return False, "tmux command timed out"
    except Exception as e:
        return False, str(e)


def ensure_session(session_name: str = _DEFAULT_SESSION) -> tuple[bool, str]:
    """Ensure tmux session exists. Creates it if needed."""
    # Check if session exists
    success, output = _tmux_command(["has-session", "-t", session_name])
    if success:
        return True, f"Session '{session_name}' already exists"

    # Create new session (detached)
    success, output = _tmux_command(
        ["new-session", "-d", "-s", session_name, "-c", str(Path.cwd())]
    )
    if success:
        return True, f"Created session '{session_name}'"
    return False, output


def spawn_agent(
    agent_type: str,
    task: str,
    window_name: str | None = None,
    session_name: str = _DEFAULT_SESSION,
) -> tuple[bool, str]:
    """
    Spawn an agent in a new tmux window/pane.

    Args:
        agent_type: 'aider', 'goose', 'autogpt', 'shell'
        task: The task description/command
        window_name: Optional window name (defaults to agent_type-timestamp)
        session_name: Tmux session name

    Returns:
        (success, message)
    """
    import time

    # Ensure session exists
    ensure_session(session_name)

    # Generate window name
    if window_name is None:
        timestamp = int(time.time())
        window_name = f"{agent_type}-{timestamp}"

    # Build command based on agent type — use shlex.quote to prevent shell injection
    safe_task = shlex.quote(task)
    if agent_type == "aider":
        cmd = f"aider --message {safe_task}"
    elif agent_type == "goose":
        cmd = f"goose run {safe_task}"
    elif agent_type == "autogpt":
        cmd = f"python -m autogpt run --continuous --task {safe_task}"
    elif agent_type == "shell":
        return False, "Direct shell execution is disabled for security reasons"
    else:
        return False, f"Unknown agent type: {agent_type}"

    # Create new window with command
    success, output = _tmux_command(
        ["new-window", "-t", session_name, "-n", window_name, "-c", str(Path.cwd()), cmd]
    )

    if success:
        return True, f"Spawned {agent_type} in {session_name}:{window_name}"
    return False, f"Failed to spawn: {output}"


def list_agents(session_name: str = _DEFAULT_SESSION) -> tuple[bool, list[dict]]:
    """List all agent windows in the session."""
    success, output = _tmux_command(
        [
            "list-windows",
            "-t",
            session_name,
            "-F",
            "#{window_index}|#{window_name}|#{pane_pid}|#{window_active}",
        ]
    )

    if not success:
        return False, []

    agents = []
    for line in output.split("\n"):
        if "|" in line:
            parts = line.split("|")
            agents.append(
                {"index": parts[0], "name": parts[1], "pid": parts[2], "active": parts[3] == "1"}
            )

    return True, agents


def kill_agent(window_name: str, session_name: str = _DEFAULT_SESSION) -> tuple[bool, str]:
    """Kill a specific agent window."""
    success, output = _tmux_command(["kill-window", "-t", f"{session_name}:{window_name}"])

    if success:
        return True, f"Killed window {window_name}"
    return False, output


def get_agent_log(window_name: str, session_name: str = _DEFAULT_SESSION) -> tuple[bool, str]:
    """Capture output from an agent window."""
    success, output = _tmux_command(["capture-pane", "-t", f"{session_name}:{window_name}", "-p"])

    return success, output


# MCP Tool definitions for Claude Code integration
MCP_TOOLS = {
    "tmux_spawn_agent": {
        "description": "Spawn an agent (aider, goose, autogpt) in a tmux window for background execution",
        "parameters": {
            "agent_type": {"type": "string", "enum": ["aider", "goose", "autogpt", "shell"]},
            "task": {"type": "string"},
            "window_name": {"type": "string", "optional": True},
            "session_name": {"type": "string", "default": _DEFAULT_SESSION},
        },
    },
    "tmux_list_agents": {
        "description": "List all running agent windows",
        "parameters": {"session_name": {"type": "string", "default": _DEFAULT_SESSION}},
    },
    "tmux_kill_agent": {
        "description": "Kill a specific agent window",
        "parameters": {
            "window_name": {"type": "string"},
            "session_name": {"type": "string", "default": _DEFAULT_SESSION},
        },
    },
    "tmux_get_log": {
        "description": "Get the output/log from an agent window",
        "parameters": {
            "window_name": {"type": "string"},
            "session_name": {"type": "string", "default": _DEFAULT_SESSION},
        },
    },
}
