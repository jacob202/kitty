"""BaseTool wrappers for code editing tools (kitty self-modification)."""

from __future__ import annotations

from typing import Any

from src.tools.base import BaseTool, ToolResult
from src.tools.code_edit import list_kitty_files, patch_agent_json, read_kitty_file, write_kitty_file

__all__ = ["CodeReadTool", "CodeWriteTool", "CodeListTool", "AgentPatchTool"]


class CodeReadTool(BaseTool):
    """Wrapper around read_kitty_file for reading code files."""

    @property
    def name(self) -> str:
        return "code_read"

    @property
    def command(self) -> str:
        return "/coderead"

    @property
    def description(self) -> str:
        return "Read a file relative to the kitty project root."

    def execute(self, **kwargs: Any) -> ToolResult:
        path = kwargs.get("path", "")
        if not path:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error="No path provided")
        try:
            result = read_kitty_file(path)
            return ToolResult(ok=True, tool=self.name, args=kwargs, result={"output": result})
        except Exception as e:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error=str(e))


class CodeWriteTool(BaseTool):
    """Wrapper around write_kitty_file for safe code modifications."""

    @property
    def name(self) -> str:
        return "code_write"

    @property
    def command(self) -> str:
        return "/codewrite"

    @property
    def description(self) -> str:
        return "Write content to a file in the kitty project (with backup and validation)."

    @property
    def requires_confirmation(self) -> bool:
        return True

    def execute(self, **kwargs: Any) -> ToolResult:
        path = kwargs.get("path", "")
        content = kwargs.get("content", "")
        confirmed = kwargs.get("confirmed", False)
        if not path:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error="No path provided")
        try:
            result = write_kitty_file(path, content, confirmed=confirmed)
            return ToolResult(ok=True, tool=self.name, args=kwargs, result={"output": result})
        except Exception as e:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error=str(e))


class CodeListTool(BaseTool):
    """Wrapper around list_kitty_files for listing project files."""

    @property
    def name(self) -> str:
        return "code_ls"

    @property
    def command(self) -> str:
        return "/codels"

    @property
    def description(self) -> str:
        return "List files in the kitty project directory."

    def execute(self, **kwargs: Any) -> ToolResult:
        subdir = kwargs.get("subdir", kwargs.get("path", ""))
        try:
            result = list_kitty_files(subdir)
            return ToolResult(ok=True, tool=self.name, args=kwargs, result={"output": result})
        except Exception as e:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error=str(e))


class AgentPatchTool(BaseTool):
    """Wrapper around patch_agent_json for modifying agent configurations."""

    @property
    def name(self) -> str:
        return "agent_patch"

    @property
    def command(self) -> str:
        return "/agentpatch"

    @property
    def description(self) -> str:
        return "Patch a specific field in an agent JSON configuration."

    @property
    def requires_confirmation(self) -> bool:
        return True

    def execute(self, **kwargs: Any) -> ToolResult:
        agent = kwargs.get("agent", "")
        field = kwargs.get("field", "")
        operation = kwargs.get("operation", "set")
        value = kwargs.get("value", "")
        if not agent:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error="No agent name provided")
        try:
            result = patch_agent_json(agent, field, operation, value)
            return ToolResult(ok=True, tool=self.name, args=kwargs, result={"output": result})
        except Exception as e:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error=str(e))
