"""BaseTool wrapper for OBD Fusion CSV log analysis."""

from __future__ import annotations

from typing import Any

from src.tools.base import BaseTool, ToolResult
from src.tools.obd_parser import (
    RIDGELINE_VIN,
    analyze_latest,
    analyze_log,
    list_logs,
    trend_summary,
)

__all__ = ["OBDTool"]


class OBDTool(BaseTool):
    """Wrapper around OBD parser functions with sub-operation dispatch."""

    @property
    def name(self) -> str:
        return "obd_tool"

    @property
    def command(self) -> str:
        return "/obd"

    @property
    def description(self) -> str:
        return "Analyze OBD-II diagnostic logs from the Ridgeline. Operations: list, latest, trend, analyze."

    def execute(self, **kwargs: Any) -> ToolResult:
        operation = kwargs.get("operation", "latest")
        vin = kwargs.get("vin", RIDGELINE_VIN)
        try:
            if operation == "list":
                limit = kwargs.get("limit", 10)
                result = list_logs(vin=vin, limit=limit)
            elif operation == "latest":
                result = analyze_latest(vin=vin)
            elif operation == "trend":
                last_n = kwargs.get("last_n", 10)
                result = trend_summary(vin=vin, last_n=last_n)
            elif operation == "analyze":
                path = kwargs.get("path", "")
                if not path:
                    return ToolResult(ok=False, tool=self.name, args=kwargs, error="No path provided for analyze")
                fast = kwargs.get("fast", False)
                result = analyze_log(path=path, fast=fast)
            else:
                return ToolResult(ok=False, tool=self.name, args=kwargs, error=f"Unknown operation: {operation}")
            return ToolResult(ok=True, tool=self.name, args=kwargs, result={"output": str(result)})
        except Exception as e:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error=str(e))
