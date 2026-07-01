"""Read-only current-state composition for /state/now."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = 1


def compose_now() -> dict[str, Any]:
    return {
        "generated_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "schema_version": SCHEMA_VERSION,
        "sections": {
            "today": {"status": "empty", "items": []},
            "open_loops": {"status": "empty", "items": []},
            "recent_activity": {"status": "empty", "items": []},
            "runtime_health": {"status": "error", "detail": "not yet wired"},
        },
        "errors": [],
    }
