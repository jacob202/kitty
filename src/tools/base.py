"""Base class for all Kitty tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ToolResult:
    ok: bool
    tool: str
    args: dict
    result: dict | None = None
    error: str | None = None
    denied: bool = False


class BaseTool(ABC):
    """Abstract base class for all Kitty tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the tool (e.g., 'list_directory')."""
        pass

    @property
    @abstractmethod
    def command(self) -> str:
        """Slash command for this tool (e.g., '/ls')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Short description of the tool."""
        pass

    @property
    def requires_confirmation(self) -> bool:
        """Whether this tool requires explicit user confirmation before execution."""
        return False

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given arguments."""
        pass
