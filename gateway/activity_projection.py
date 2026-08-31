"""Read-only projection of Kitty work that already belongs to existing authorities."""

from __future__ import annotations

from typing import Any, Callable

from gateway.paths import BUILDER_QUEUE_DB

_STATE_PRIORITY = {"waiting": 0, "running": 1, "failed": 2, "completed": 3}


def _bounded(value: Any, limit: int = 240) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:limit]


def _source_state(fn: Callable[[], list[dict[str, Any]]]) -> tuple[list[dict[str, Any]], dict[str, str | None]]:
    try:
        return fn(), {"state": "available", "reason": None}
    except Exception as exc:
        return [], {"state": "unavailable", "reason": _bounded(exc)}


def _action_items() -> list[dict[str, Any]]:
    from gateway import action_queue

    rows = action_queue.list_actions(limit=30)
    mapping = {
        "proposed": "waiting",
        "approved": "running",
        "executing": "running",
        "executed": "completed",
        "rejected": "completed",
        "failed": "failed",
        "outcome_unknown": "failed",
    }
    return [
        {
            "id": f"action:{row['id']}",
            "source": "action",
            "source_id": str(row["id"]),
            "title": _bounded(row.get("title"), 120) or "Kitty action",
            "detail": _bounded(row.get("preview")),
            "state": mapping.get(str(row.get("status")), "running"),
            "raw_state": str(row.get("status") or "unknown"),
            "occurred_at": float(row.get("executed_at") or row.get("decided_at") or row.get("created_at") or 0),
            "destination": "home",
        }
        for row in rows
    ]


def _automation_items() -> list[dict[str, Any]]:
    from gateway import automation_runs

    rows = automation_runs.list_runs(limit=30)
    failed = {"failed", "interrupted", "action_unavailable", "source_unavailable", "policy_refused"}
    completed = {"completed", "condition_false", "watch_disabled"}
    items = []
    for row in rows:
        raw = str(row.get("status") or "unknown")
        state = "running" if raw == "running" else "failed" if raw in failed else "completed" if raw in completed else "running"
        title = _bounded(row.get("action"), 120) or "Automation run"
        automation_id = _bounded(row.get("automation_id"), 120)
        detail = _bounded(row.get("error")) or (f"Automation {automation_id}" if automation_id else None)
        items.append({
            "id": f"automation:{row['id']}",
            "source": "automation",
            "source_id": str(row["id"]),
            "title": title,
            "detail": detail,
            "state": state,
            "raw_state": raw,
            "occurred_at": float(row.get("completed_at") or row.get("started_at") or row.get("created_at") or 0),
            "destination": "automations",
        })
    return items


def _agent_items() -> list[dict[str, Any]]:
    from gateway import agent_runner

    rows = agent_runner.list_agents(limit=30)
    items = []
    for row in rows:
        raw = str(row.get("status") or "unknown")
        if raw == "active":
            state = "running"
        elif raw == "completed":
            state = "completed"
        elif raw in {"failed", "interrupted", "cancelled"}:
            state = "failed"
        else:
            state = "running"
        items.append({
            "id": f"agent:{row['session_id']}",
            "source": "agent",
            "source_id": str(row["session_id"]),
            "title": _bounded(row.get("goal"), 120) or "Agent session",
            "detail": None,
            "state": state,
            "raw_state": raw,
            "occurred_at": float(row.get("updated_at") or row.get("created_at") or 0),
            "destination": "agents",
        })
    return items


def _builder_items() -> list[dict[str, Any]]:
    from gateway.builder_status import build_control_plane_summary

    snapshot = build_control_plane_summary(db_path=BUILDER_QUEUE_DB)
    items = []
    for initiative in snapshot.get("initiatives", []):
        raw = str(initiative.get("state") or "unknown")
        if raw in {"paused", "blocked"}:
            state = "waiting"
        elif raw in {"failed", "exhausted"}:
            state = "failed"
        elif raw in {"completed", "done"}:
            state = "completed"
        else:
            state = "running"
        items.append({
            "id": f"builder:{initiative.get('initiative_id')}",
            "source": "builder",
            "source_id": str(initiative.get("initiative_id") or ""),
            "title": _bounded(initiative.get("title"), 120) or "Builder initiative",
            "detail": _bounded(initiative.get("pause_reason")),
            "state": state,
            "raw_state": raw,
            "occurred_at": float(initiative.get("updated_at") or 0),
            "destination": "work",
        })
    return items


def build_activity_projection(*, limit: int = 40) -> dict[str, Any]:
    collectors = {
        "actions": _action_items,
        "automations": _automation_items,
        "agents": _agent_items,
        "builder": _builder_items,
    }
    items: list[dict[str, Any]] = []
    sources: dict[str, dict[str, str | None]] = {}
    for name, collector in collectors.items():
        projected, source = _source_state(collector)
        items.extend(projected)
        sources[name] = source

    items.sort(key=lambda item: (_STATE_PRIORITY[item["state"]], -float(item["occurred_at"])))
    items = items[: max(1, min(int(limit), 100))]
    counts = {state: sum(1 for item in items if item["state"] == state) for state in _STATE_PRIORITY}
    return {"items": items, "counts": {"total": len(items), **counts}, "sources": sources}
