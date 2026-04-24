"""BaseTool wrappers for macOS-specific tools (apps, calendar, reminders, messages, obsidian)."""

from __future__ import annotations

from typing import Any

from src.tools.base import BaseTool, ToolResult
from src.tools.system_tools import AppTool, CalendarTool, MessagesTool, ObsidianTool, RemindersTool

__all__ = [
    "AppToolMT",
    "CalendarToolMT",
    "CalendarCreateToolMT",
    "RemindersToolMT",
    "MessagesToolMT",
    "ObsidianToolMT",
]


class AppToolMT(BaseTool):
    """Wrapper around AppTool for macOS app control."""

    @property
    def name(self) -> str:
        return "app_control"

    @property
    def command(self) -> str:
        return "/app"

    @property
    def description(self) -> str:
        return "Open, close, or list macOS applications."

    @property
    def requires_confirmation(self) -> bool:
        return True

    def execute(self, **kwargs: Any) -> ToolResult:
        at = AppTool()
        try:
            action = kwargs.get("action", kwargs.get("operation", ""))
            if action == "open" or "open" in kwargs:
                result = at.open(app=kwargs.get("app", kwargs.get("name", "")))
            elif action == "close" or "close" in kwargs:
                result = at.close(app=kwargs.get("app", kwargs.get("name", "")))
            elif action == "list" or action == "list_running":
                result = at.list_running()
            elif action == "applescript" or kwargs.get("script"):
                result = at.applescript(script=kwargs.get("script", ""))
            else:
                result = at.list_running()
            return ToolResult(ok=True, tool=self.name, args=kwargs, result={"output": result})
        except Exception as e:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error=str(e))


class CalendarToolMT(BaseTool):
    """Wrapper around CalendarTool.list_events()."""

    @property
    def name(self) -> str:
        return "calendar_list"

    @property
    def command(self) -> str:
        return "/calendar"

    @property
    def description(self) -> str:
        return "List upcoming calendar events."

    def execute(self, **kwargs: Any) -> ToolResult:
        try:
            result = CalendarTool().list_events(days_ahead=kwargs.get("days_ahead", 7))
            return ToolResult(ok=True, tool=self.name, args=kwargs, result={"output": result})
        except Exception as e:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error=str(e))


class CalendarCreateToolMT(BaseTool):
    """Wrapper around CalendarTool.create_event()."""

    @property
    def name(self) -> str:
        return "calendar_create"

    @property
    def command(self) -> str:
        return "/calendarcreate"

    @property
    def description(self) -> str:
        return "Create a new calendar event."

    def execute(self, **kwargs: Any) -> ToolResult:
        try:
            result = CalendarTool().create_event(
                title=kwargs.get("title", ""),
                start=kwargs.get("start", ""),
                duration_minutes=kwargs.get("duration_minutes", 60),
                calendar=kwargs.get("calendar", ""),
                notes=kwargs.get("notes", ""),
            )
            return ToolResult(ok=True, tool=self.name, args=kwargs, result={"output": result})
        except Exception as e:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error=str(e))


class RemindersToolMT(BaseTool):
    """Wrapper around RemindersTool for creating reminders."""

    @property
    def name(self) -> str:
        return "reminder_create"

    @property
    def command(self) -> str:
        return "/remind"

    @property
    def description(self) -> str:
        return "Create a macOS reminder that fires as a notification."

    def execute(self, **kwargs: Any) -> ToolResult:
        try:
            result = RemindersTool().create(
                title=kwargs.get("title", kwargs.get("name", "")),
                remind_at=kwargs.get("remind_at", kwargs.get("when", "")),
                notes=kwargs.get("notes", ""),
            )
            return ToolResult(ok=True, tool=self.name, args=kwargs, result={"output": result})
        except Exception as e:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error=str(e))


class MessagesToolMT(BaseTool):
    """Wrapper around MessagesTool for sending iMessages."""

    @property
    def name(self) -> str:
        return "messages_send"

    @property
    def command(self) -> str:
        return "/msg"

    @property
    def description(self) -> str:
        return "Send an iMessage to a contact."

    @property
    def requires_confirmation(self) -> bool:
        return True

    def execute(self, **kwargs: Any) -> ToolResult:
        try:
            result = MessagesTool().send(
                to=kwargs.get("to", ""),
                text=kwargs.get("text", kwargs.get("message", "")),
            )
            return ToolResult(ok=True, tool=self.name, args=kwargs, result={"output": result})
        except Exception as e:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error=str(e))


class ObsidianToolMT(BaseTool):
    """Single wrapper for all Obsidian operations — registered under 5 aliases."""

    @property
    def name(self) -> str:
        return "obsidian_tool"

    @property
    def command(self) -> str:
        return "/obsidian"

    @property
    def description(self) -> str:
        return "Read, create, append, search, and list Obsidian vault notes."

    def execute(self, **kwargs: Any) -> ToolResult:
        from src.config.config_loader import get_config

        vault_path = get_config("obsidian_vault_path", "")
        ot = ObsidianTool(vault_path=vault_path)
        try:
            # Infer sub-operation from kwargs keys
            if kwargs.get("query"):
                result = ot.search_notes(query=kwargs.get("query", ""))
            elif kwargs.get("folder") is not None:
                result = ot.list_notes(folder=kwargs.get("folder", ""))
            elif kwargs.get("content") and kwargs.get("path"):
                result = ot.append_note(path=kwargs.get("path", ""), content=kwargs.get("content", ""))
            elif kwargs.get("path"):
                result = ot.read_note(path=kwargs.get("path", ""))
            else:
                result = ot.read_note(path=kwargs.get("path", ""))
            return ToolResult(ok=True, tool=self.name, args=kwargs, result={"output": result})
        except Exception as e:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error=str(e))
