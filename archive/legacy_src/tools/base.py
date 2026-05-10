"""Base class for all Kitty tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolResult:
    ok: bool
    tool: str
    args: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None
    denied: bool = False


class BaseTool(ABC):
    """Abstract base class for all Kitty tools."""

    _registry: dict[str, type[BaseTool]] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        name = getattr(cls, "name", None)
        if name is not None and isinstance(name, property):
            # Need to instantiate to get the name — register via instance
            pass
        elif name is not None:
            BaseTool._registry[name] = cls

    @classmethod
    def get_tool(cls, name: str) -> type[BaseTool] | None:
        return cls._registry.get(name)

    @classmethod
    def list_tools(cls) -> dict[str, str]:
        return {
            name: getattr(tool_cls, "description", "") or ""
            for name, tool_cls in cls._registry.items()
        }

    @classmethod
    def get_tool_by_command(cls, command: str) -> type[BaseTool] | None:
        for tool_cls in cls._registry.values():
            try:
                inst = tool_cls()
                if getattr(inst, "command", None) == command:
                    return tool_cls
            except Exception:
                continue
        return None

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
    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given arguments."""
        pass
