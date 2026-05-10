"""Search files tool."""

import json
from pathlib import Path
from typing import Any

from src.tools import tool_registry
from src.tools.base import BaseTool, ToolResult

INDEX_FILE = Path("data/cache/file_index.json")


class IndexSearchTool(BaseTool):
    """Tool for searching file index (fast, pre-built)."""

    @property
    def name(self) -> str:
        return "index_search"

    @property
    def description(self) -> str:
        return "Search pre-built file index (much faster than glob)."

    def execute(self, **kwargs: Any) -> ToolResult:
        pattern = kwargs.get("pattern", "")
        if not pattern:
            return ToolResult(ok=False, tool=self.name, result="", error="Missing pattern")

        try:
            if INDEX_FILE.exists():
                with open(INDEX_FILE) as f:
                    data = json.load(f)
            else:
                return ToolResult(ok=False, tool=self.name, result="", error="No index. Run: python scripts/build_file_index.py")

            matches = []
            for ext, files in data.items():
                for f in files:
                    if "evals/" in f or "garage-ui/" in f:
                        continue
                    if pattern.lower() in f.lower():
                        matches.append(f)
                        if len(matches) >= 50:
                            break
                if len(matches) >= 50:
                    break

            return ToolResult(ok=True, tool=self.name, result=f"Found {len(matches)} matches:\n" + "\n".join(matches[:20]))
        except Exception as e:
            return ToolResult(ok=False, tool=self.name, result="", error=str(e))
