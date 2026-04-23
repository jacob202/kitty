"""Permissioned local tool registry for safe file operations."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class ToolPermission(Enum):
    LIST_DIRECTORY = "list_directory"
    READ_FILE = "read_file"
    SEARCH_FILES = "search_files"


TOOL_PERMISSIONS = {
    "list_directory": {ToolPermission.LIST_DIRECTORY},
    "read_file": {ToolPermission.READ_FILE},
    "search_files": {ToolPermission.SEARCH_FILES},
}


@dataclass
class ToolResult:
    ok: bool
    tool: str
    args: dict
    result: dict | None = None
    error: str | None = None
    denied: bool = False


@dataclass
class ToolRegistry:
    """Sandboxed tool registry with path restrictions and action logging."""

    allowed_root: Path = field(default_factory=lambda: Path.cwd())
    log_path: Path = field(default_factory=lambda: Path("data/activity/actions.jsonl"))

    def __post_init__(self):
        self.allowed_root = self.allowed_root.resolve()
        self.log_path = Path(self.log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _is_safe_path(self, path: Path) -> bool:
        try:
            resolved = path.resolve()
            return resolved.is_relative_to(self.allowed_root)
        except (ValueError, OSError):
            return False

    def _has_traversal(self, path: Path) -> bool:
        parts = str(path).replace("\\", "/").split("/")
        return os.pardir in parts

    def permissions_for(self, tool: str) -> set[ToolPermission]:
        return set(TOOL_PERMISSIONS.get(tool, set()))

    def describe_tools(self) -> dict:
        return {
            name: {"permissions": sorted(permission.value for permission in permissions)}
            for name, permissions in TOOL_PERMISSIONS.items()
        }

    def _log_action(
        self,
        tool: str,
        args: dict,
        result: dict | None,
        denied: bool,
        error: str | None = None,
    ):
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool": tool,
            "args": {k: str(v) for k, v in args.items()},
            "denied": denied,
            "ok": result is not None and not denied,
        }
        if error:
            record["error"] = error
        if result:
            record["result_summary"] = self._summarize_result(tool, result)
        try:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=True) + "\n")
        except Exception:
            pass

    def _summarize_result(self, tool: str, result: dict) -> dict:
        if tool == "list_directory":
            names = result.get("entries", [])
            return {"count": len(names), "files": names[:10]}
        if tool == "read_file":
            content = result.get("content", "")
            return {"size": len(content), "preview": content[:200]}
        if tool == "search_files":
            matches = result.get("matches", [])
            return {"match_count": len(matches), "files_searched": result.get("files_searched", 0)}
        return {}

    def _deny(self, tool: str, args: dict, reason: str) -> ToolResult:
        self._log_action(tool, args, None, denied=True, error=reason)
        return ToolResult(
            ok=False,
            tool=tool,
            args=args,
            denied=True,
            error=f"Access denied: {reason}",
        )

    def list_directory(self, path: str = ".") -> ToolResult:
        args = {"path": path}
        try:
            target = Path(path)
            if self._has_traversal(target):
                return self._deny("list_directory", args, "path traversal not allowed")
            if not self._is_safe_path(self.allowed_root / target):
                return self._deny("list_directory", args, "outside allowed directory")
            full_path = (self.allowed_root / target).resolve()
            if not full_path.is_dir():
                return self._deny("list_directory", args, "not a directory")
            entries = []
            for entry in sorted(full_path.iterdir()):
                entries.append(entry.name)
            result = {"path": str(full_path.relative_to(self.allowed_root)), "entries": entries}
            self._log_action("list_directory", args, result, denied=False)
            return ToolResult(ok=True, tool="list_directory", args=args, result=result)
        except Exception as e:
            return self._deny("list_directory", args, str(e))

    def read_file(self, path: str) -> ToolResult:
        args = {"path": path}
        try:
            target = Path(path)
            if self._has_traversal(target):
                return self._deny("read_file", args, "path traversal not allowed")
            if not self._is_safe_path(self.allowed_root / target):
                return self._deny("read_file", args, "outside allowed directory")
            full_path = (self.allowed_root / target).resolve()
            if not full_path.is_file():
                return self._deny("read_file", args, "not a file")
            try:
                content = full_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                return self._deny("read_file", args, "file is not readable as text")
            result = {
                "path": str(full_path.relative_to(self.allowed_root)),
                "content": content,
                "size": len(content),
            }
            self._log_action("read_file", args, result, denied=False)
            return ToolResult(ok=True, tool="read_file", args=args, result=result)
        except Exception as e:
            return self._deny("read_file", args, str(e))

    def search_files(
        self,
        query: str,
        path: str = ".",
        extensions: list[str] | None = None,
        max_results: int = 50,
    ) -> ToolResult:
        args = {"query": query, "path": path, "extensions": extensions, "max_results": max_results}
        try:
            if not query.strip():
                return self._deny("search_files", args, "query is required")
            target = Path(path)
            if self._has_traversal(target):
                return self._deny("search_files", args, "path traversal not allowed")
            if not self._is_safe_path(self.allowed_root / target):
                return self._deny("search_files", args, "outside allowed directory")
            full_path = (self.allowed_root / target).resolve()
            if not full_path.is_dir():
                return self._deny("search_files", args, "not a directory")
            query_lower = query.lower()
            extensions = extensions or [".py", ".md", ".txt", ".json", ".toml", ".yaml", ".yml"]
            matches = []
            files_searched = 0
            for ext in extensions:
                for file_path in full_path.rglob(f"*{ext}"):
                    if len(matches) >= max_results:
                        break
                    if not self._is_safe_path(file_path):
                        continue
                    try:
                        files_searched += 1
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        if query_lower in content.lower():
                            lines = content.splitlines()
                            for i, line in enumerate(lines, 1):
                                if query_lower in line.lower():
                                    matches.append(
                                        {
                                            "file": str(file_path.relative_to(self.allowed_root)),
                                            "line": i,
                                            "text": line.strip()[:200],
                                        }
                                    )
                                    if len(matches) >= max_results:
                                        break
                    except Exception:
                        pass
                    if len(matches) >= max_results:
                        break
                if len(matches) >= max_results:
                    break
            result = {
                "query": query,
                "path": str(full_path.relative_to(self.allowed_root)),
                "matches": matches,
                "match_count": len(matches),
                "files_searched": files_searched,
            }
            self._log_action("search_files", args, result, denied=False)
            return ToolResult(ok=True, tool="search_files", args=args, result=result)
        except Exception as e:
            return self._deny("search_files", args, str(e))


_registry: ToolRegistry | None = None


def get_registry(
    allowed_root: Path | None = None,
    log_path: Path | None = None,
) -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry(
            allowed_root=allowed_root or Path.cwd(),
            log_path=log_path or Path("data/activity/actions.jsonl"),
        )
    return _registry
