"""BaseTool wrappers for system tools (shell, file, server)."""

from __future__ import annotations

from typing import Any

from src.tools.base import BaseTool, ToolResult
from src.tools.system_tools import FileTool, ServerTool, ShellTool

__all__ = ["ShellToolST", "FileToolST", "FileReadTool", "FileWriteTool", "ServerToolST"]


class ShellToolST(BaseTool):
    """Wrapper around ShellTool for shell command execution."""

    @property
    def name(self) -> str:
        return "shell_exec"

    @property
    def command(self) -> str:
        return "/sh"

    @property
    def description(self) -> str:
        return "Execute a shell command with validation and timeout."

    @property
    def requires_confirmation(self) -> bool:
        return True

    def execute(self, **kwargs: Any) -> ToolResult:
        cmd = kwargs.get("command") or kwargs.get("cmd") or ""
        if not cmd:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error="No command provided")
        try:
            result = ShellTool().execute(command=cmd)
            return ToolResult(ok=True, tool=self.name, args=kwargs, result={"output": result})
        except Exception as e:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error=str(e))


class FileToolST(BaseTool):
    """Wrapper around FileTool with multi-operation dispatch."""

    @property
    def name(self) -> str:
        return "file_ops"

    @property
    def command(self) -> str:
        return "/file"

    @property
    def description(self) -> str:
        return "Read, write, or list files under the home directory."

    def execute(self, **kwargs: Any) -> ToolResult:
        ft = FileTool()
        try:
            operation = kwargs.get("operation", "")
            if operation == "read" or ("path" in kwargs and "content" not in kwargs and kwargs.get("path", "")):
                result = ft.read(path=kwargs.get("path", ""), max_lines=kwargs.get("max_lines", 150))
            elif operation == "write" or "content" in kwargs:
                result = ft.write(path=kwargs.get("path", ""), content=kwargs.get("content", ""))
            elif operation == "list" or "pattern" in kwargs:
                result = ft.list(path=kwargs.get("path", "~/Desktop"), pattern=kwargs.get("pattern", "*"))
            else:
                result = ft.list(path=kwargs.get("path", "~/Desktop"), pattern=kwargs.get("pattern", "*"))
            return ToolResult(ok=True, tool=self.name, args=kwargs, result={"output": result})
        except Exception as e:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error=str(e))


class FileReadTool(BaseTool):
    """Wrapper around FileTool.read() for reading file content."""

    @property
    def name(self) -> str:
        return "file_read"

    @property
    def command(self) -> str:
        return "/fileread"

    @property
    def description(self) -> str:
        return "Read the contents of a file."

    def execute(self, **kwargs: Any) -> ToolResult:
        try:
            result = FileTool().read(path=kwargs.get("path", ""), max_lines=kwargs.get("max_lines", 150))
            return ToolResult(ok=True, tool=self.name, args=kwargs, result={"output": result})
        except Exception as e:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error=str(e))


class FileWriteTool(BaseTool):
    """Wrapper around FileTool.write() for writing content to a file."""

    @property
    def name(self) -> str:
        return "file_write"

    @property
    def command(self) -> str:
        return "/filewrite"

    @property
    def description(self) -> str:
        return "Write content to a file (with overwrite confirmation)."

    @property
    def requires_confirmation(self) -> bool:
        return True

    def execute(self, **kwargs: Any) -> ToolResult:
        try:
            result = FileTool().write(
                path=kwargs.get("path", ""),
                content=kwargs.get("content", ""),
            )
            return ToolResult(ok=True, tool=self.name, args=kwargs, result={"output": result})
        except Exception as e:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error=str(e))


class ServerToolST(BaseTool):
    """Wrapper around ServerTool for HTTP/health checks."""

    @property
    def name(self) -> str:
        return "server_status"

    @property
    def command(self) -> str:
        return "/server"

    @property
    def description(self) -> str:
        return "Check status of known services or make HTTP requests."

    def execute(self, **kwargs: Any) -> ToolResult:
        try:
            service = kwargs.get("service")
            url = kwargs.get("url")
            if url:
                result = ServerTool().request(
                    url=url,
                    method=kwargs.get("method", "GET"),
                    body=kwargs.get("body"),
                    headers=kwargs.get("headers"),
                )
            else:
                result = ServerTool().status(service=service)
            return ToolResult(ok=True, tool=self.name, args=kwargs, result={"output": result})
        except Exception as e:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error=str(e))
