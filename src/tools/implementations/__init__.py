"""Registration hub for all BaseTool implementation wrappers.

This module imports all wrapper classes from the implementation submodules
and registers each one explicitly into BaseTool._registry by its .name property.

ObsidianToolMT gets 5 additional alias registrations so that tool name lookups
like "obsidian_read" and "obsidian_search" resolve to the same class, which
infers the sub-operation from kwargs keys at execution time.
"""

from __future__ import annotations

from src.tools.base import BaseTool

from .code_tools import AgentPatchTool, CodeListTool, CodeReadTool, CodeWriteTool
from .macos_tools import (
    AppToolMT,
    CalendarCreateToolMT,
    CalendarToolMT,
    MessagesToolMT,
    ObsidianToolMT,
    RemindersToolMT,
)
from .media_tools import ImageGenTool
from .obd_tools import OBDTool
from .system_tools import FileReadTool, FileToolST, FileWriteTool, ServerToolST, ShellToolST
from .web_tools import DeepSearchTool, WebSearchTool

__all__ = [
    "ShellToolST",
    "FileToolST",
    "FileReadTool",
    "FileWriteTool",
    "ServerToolST",
    "AppToolMT",
    "CalendarToolMT",
    "CalendarCreateToolMT",
    "RemindersToolMT",
    "MessagesToolMT",
    "ObsidianToolMT",
    "WebSearchTool",
    "DeepSearchTool",
    "CodeReadTool",
    "CodeWriteTool",
    "CodeListTool",
    "AgentPatchTool",
    "ImageGenTool",
    "OBDTool",
]

# -- Primary registration: all the class names above get registered by .name --
_ALL_CLASSES: list[type[BaseTool]] = [
    ShellToolST,
    FileToolST,
    FileReadTool,
    FileWriteTool,
    ServerToolST,
    AppToolMT,
    CalendarToolMT,
    CalendarCreateToolMT,
    RemindersToolMT,
    MessagesToolMT,
    ObsidianToolMT,
    WebSearchTool,
    DeepSearchTool,
    CodeReadTool,
    CodeWriteTool,
    CodeListTool,
    AgentPatchTool,
    ImageGenTool,
    OBDTool,
]


def _register_all() -> None:
    for cls in _ALL_CLASSES:
        try:
            inst = cls()
            BaseTool._registry[inst.name] = cls
        except Exception:
            pass  # skip classes that can't be instantiated at import time

    # Obsidian aliases — same class, operation inferred from kwargs keys
    for alias in ("obsidian_read", "obsidian_create", "obsidian_append", "obsidian_search", "obsidian_list"):
        BaseTool._registry[alias] = ObsidianToolMT


_register_all()
