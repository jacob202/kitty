"""Read-only projection of Kitty work that already belongs to existing authorities."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Callable

from gateway.paths import BUILDER_QUEUE_DB

_STATE_PRIORITY = {"waiting": 0, "failed": 0, "running": 1, "completed": 2}
_ACTION_ATTENTION = ("proposed", "approved", "failed", "unknown", "outcome_unknown")
_AUTOMATION_FAILURES = frozenset({
    "failed", "interrupted", "action_unavailable", "source_unavailable", "policy_refused"
})


def _bounded(value: Any, limit: int = 240) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None


def _timestamp(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip()
    try:
        return float(text)
    except ValueError:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()


def _source_state(fn: Callable[[], list[dict[str, Any]]]) -> tuple[list[dict[str, Any]], dict[str, str | None]]:
    try:
        return fn(), {"state": "available", "reason": None}
    except (OSError, sqlite3.Error) as exc:
        return [], {"state": "unavailable", "reason": _bounded(exc)}


def _dedupe(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        value = str(row.get(key))
        if value in seen:
            continue
        seen.add(value)
        result.append(row)
    return result


def _action_items() -> list[dict[str, Any]]:
    from gateway import action_queue

    rows = list(action_queue.list_actions(limit=30))
    for status in _ACTION_ATTENTION:
        rows.extend(action_queue.list_actions(status=status, limit=30))
    rows = _dedupe(rows, "id")
    mapping = {
        "proposed": "waiting",
        "approved": "waiting",
        "executing": "running",
        "executed": "completed",
        "rejected": "completed",
        "failed": "failed",
        "unknown": "failed",
        "outcome_unknown": "failed",
    }
    items = []
    for row in rows:
        raw = str(row.get("status") or "unknown")
        result = _bounded(row.get("result"))
        preview = _bounded(row.get("preview"))
        detail = result if raw in {"failed", "unknown", "outcome_unknown"} else preview
        if raw == "approved" and not detail:
            detail = "Approved and ready to run."
        items.append({
            "id": f"action:{row['id']}", "source": "action", "source_id": str(row["id"]),
            "title": _bounded(row.get("title"), 120) or "Kitty action", "detail": detail,
            "state": mapping.get(raw, "running"), "raw_state": raw,
            "occurred_at": _timestamp(row.get("executed_at") or row.get("decided_at") or row.get("created_at")),
            "destination": "home",
        })
    return items


def _automation_items() -> list[dict[str, Any]]:
    from gateway import automation_runs

    rows = list(automation_runs.list_runs(limit=30))
    rows.extend(automation_runs.list_runs(statuses=_AUTOMATION_FAILURES, limit=30))
    rows.extend(automation_runs.list_runs(statuses=frozenset({"running"}), limit=30))
    rows = _dedupe(rows, "id")
    failed = {"failed", "interrupted", "action_unavailable", "source_unavailable", "policy_refused"}
    completed = {"completed", "condition_false", "watch_disabled"}
    items = []
    for row in rows:
        raw = str(row.get("status") or "unknown")
        state = "running" if raw == "running" else "failed" if raw in failed else "completed" if raw in completed else "running"
        automation_id = _bounded(row.get("automation_id"), 120)
        items.append({
            "id": f"automation:{row['id']}", "source": "automation", "source_id": str(row["id"]),
            "title": _bounded(row.get("action"), 120) or "Automation run",
            "detail": _bounded(row.get("error")) or (f"Automation {automation_id}" if automation_id else None),
            "state": state, "raw_state": raw,
            "occurred_at": _timestamp(row.get("completed_at") or row.get("started_at") or row.get("created_at")),
            "destination": "automations",
        })
    return items


def _agent_items() -> list[dict[str, Any]]:
    from gateway import agent_runner

    items = []
    for row in agent_runner.list_agents(limit=30):
        raw = str(row.get("status") or "unknown")
        if raw == "active":
            state = "running"
        elif raw in {"completed", "cancelled"}:
            state = "completed"
        elif raw in {"failed", "interrupted"}:
            state = "failed"
        else:
            state = "running"
        items.append({
            "id": f"agent:{row['session_id']}", "source": "agent", "source_id": str(row["session_id"]),
            "title": _bounded(row.get("goal"), 120) or "Agent session", "detail": None,
            "state": state, "raw_state": raw,
            "occurred_at": _timestamp(row.get("updated_at") or row.get("created_at")), "destination": "agents",
        })
    return items


def _builder_items() -> list[dict[str, Any]]:
    from gateway.builder_status import build_control_plane_summary

    snapshot = build_control_plane_summary(db_path=BUILDER_QUEUE_DB)
    items = []
    for initiative in snapshot.get("initiatives", []):
        raw = str(initiative.get("state") or "unknown")
        superseded_by = _bounded(initiative.get("superseded_by"), 120)
        if superseded_by:
            state = "completed"
        elif raw in {"paused", "blocked"}:
            state = "waiting"
        elif raw in {"failed", "exhausted"}:
            state = "failed"
        elif raw in {"completed", "done"}:
            state = "completed"
        else:
            state = "running"
        detail = f"Superseded by {superseded_by}" if superseded_by else _bounded(initiative.get("pause_reason"))
        items.append({
            "id": f"builder:{initiative.get('initiative_id')}", "source": "builder",
            "source_id": str(initiative.get("initiative_id") or ""),
            "title": _bounded(initiative.get("title"), 120) or "Builder initiative", "detail": detail,
            "state": state, "raw_state": raw, "occurred_at": _timestamp(initiative.get("updated_at")),
            "destination": "work",
        })
    return items


def build_activity_projection(*, limit: int = 40) -> dict[str, Any]:
    collectors = {"actions": _action_items, "automations": _automation_items, "agents": _agent_items, "builder": _builder_items}
    items: list[dict[str, Any]] = []
    sources: dict[str, dict[str, str | None]] = {}
    for name, collector in collectors.items():
        projected, source = _source_state(collector)
        items.extend(projected)
        sources[name] = source

    counts = {state: sum(1 for item in items if item["state"] == state) for state in _STATE_PRIORITY}
    items.sort(key=lambda item: (_STATE_PRIORITY[item["state"]], -float(item["occurred_at"])))
    visible = items[: max(1, min(int(limit), 100))]
    return {"items": visible, "counts": {"total": len(items), **counts}, "sources": sources}
