"""Unified command engine — single resolution path for all slash commands."""

from __future__ import annotations

import difflib
import logging
import sys
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

CommandHandler = Callable[..., "CommandResult"]


@dataclass
class CommandResult:
    success: bool
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "ok": self.success,
            "response": self.message if self.success else self.error,
            "data": self.data,
        }


@dataclass
class CommandRegistration:
    name: str
    handler: CommandHandler
    description: str = ""
    visible: bool = True
    category: str = "general"


class CommandEngine:
    """Central registry and dispatch for all slash commands.

    Replaces the fragmented if/elif chain in dispatcher.py and the
    hardcoded route in commands.py with a single resolution path.
    """

    def __init__(self) -> None:
        self._commands: dict[str, CommandRegistration] = {}
        self._lock = threading.Lock()

    def register(
        self,
        name: str,
        handler: CommandHandler,
        description: str = "",
        visible: bool = True,
        category: str = "general",
    ) -> None:
        name = name.lstrip("/").lower()
        with self._lock:
            self._commands[name] = CommandRegistration(
                name=name,
                handler=handler,
                description=description,
                visible=visible,
                category=category,
            )

    def execute(
        self,
        command_string: str,
        output_mode: str = "dict",
        **context: Any,
    ) -> CommandResult:
        """Execute a command string. Returns structured result.

        Args:
            command_string: Full command including / prefix (e.g. "/stuck").
            output_mode: "dict" returns structured result for API consumers.
                         "stdout" prints to sys.stdout and returns None-like result.
            **context: Arbitrary context passed to the handler (e.g. sup, orch).
        """
        command_string = command_string.strip()

        if not command_string.startswith("/"):
            return CommandResult(
                success=False,
                error=f"Not a command: {command_string}",
            )

        parts = command_string.split(maxsplit=1)
        cmd_name = parts[0].lstrip("/").lower()
        args = parts[1] if len(parts) > 1 else ""

        handler = self._get_handler(cmd_name)
        if handler is None:
            similar = self.get_similar(cmd_name)
            if similar:
                msg = f"Unknown command: {command_string.split()[0]}. Did you mean: {', '.join(similar)}?"
            else:
                msg = f"Unknown command: {command_string.split()[0]}. Type /help for available commands."
            if output_mode == "stdout":
                sys.stdout.write(msg + "\n")
            return CommandResult(success=False, error=msg, data={"similar": similar})

        try:
            result = handler(args, **context)
            if output_mode == "stdout" and result.message:
                sys.stdout.write(result.message + "\n")
            return result
        except Exception:
            logger.exception("Command '%s' failed", cmd_name)
            msg = f"Error processing command: {cmd_name}"
            if output_mode == "stdout":
                sys.stdout.write(msg + "\n")
            return CommandResult(success=False, error=msg)

    def _get_handler(self, name: str) -> CommandHandler | None:
        registration = self._commands.get(name)
        return registration.handler if registration else None

    def get_similar(self, name: str, n: int = 3, cutoff: float = 0.6) -> list[str]:
        return difflib.get_close_matches(name, list(self._commands.keys()), n=n, cutoff=cutoff)

    def get_help(self) -> str:
        lines = ["**Commands**"]
        registrations = sorted(
            [r for r in self._commands.values() if r.visible],
            key=lambda r: r.name,
        )
        for r in registrations:
            lines.append(f"- `/{r.name}` — {r.description}")
        return "\n".join(lines)

    def command_names(self) -> list[str]:
        return list(self._commands.keys())

    def visible_count(self) -> int:
        return sum(1 for r in self._commands.values() if r.visible)


_default_engine: CommandEngine | None = None
_engine_lock = threading.Lock()


def get_command_engine() -> CommandEngine:
    global _default_engine
    with _engine_lock:
        if _default_engine is None:
            _default_engine = CommandEngine()
        return _default_engine
