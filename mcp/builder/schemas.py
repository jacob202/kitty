"""Shared public response helpers for the KittyBuilder MCP bridge."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = 1
MCP_ARTIFACT_MARKER = "\nKITTY_MCP_V1:"


def fresh_at() -> str:
    return datetime.now(UTC).isoformat()


def receipt(
    operation: str,
    *,
    ok: bool,
    state: str | None = None,
    summary: str | None = None,
    error_code: str | None = None,
    error: str | None = None,
    next_action: str | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Build the common bounded MCP mutation/read receipt shape.

    Transport success is never domain success: callers must inspect ``ok`` and
    ``state``. Unknown values remain ``None`` rather than being converted to a
    fabricated success/zero value.
    """
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "ok": ok,
        "operation": operation,
        "state": state,
        "summary": summary,
        "error_code": error_code,
        "error": error,
        "next_action": next_action,
        "fresh_at": fresh_at(),
    }
    result.update(fields)
    return result
