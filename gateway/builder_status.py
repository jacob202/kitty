"""Bounded, read-only Builder status projection for the Kitty runtime API.

This module deliberately reads the Builder's durable tables rather than asking
the client to reconstruct state from queue rows. It is a projection, not a new
state machine: task, attempt, run, lease, and publication lifecycles remain
owned by their existing Builder modules.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from gateway import builder_attempt as ba
from gateway import builder_initiative as bi
from gateway import builder_queue as bq

SCHEMA_VERSION = 1
_MESSAGE_CAP = 500
_PATH_PATTERN = re.compile(r"(?<![A-Za-z0-9_])/(?:[^\s/]+/)+[^\s/]+")
_IDENTITY_RUN_STATES = frozenset({bq.RUN_LEASE_LOST, bq.RUN_SCOPE_VIOLATION})


def build_status_snapshot(*, db_path: Path | None = None) -> dict[str, Any]:
    """Return a deterministic, bounded snapshot of durable Builder status.

    The read budget is fixed per packet: aggregate attempt counts, the two
    newest attempts, the current lease, and the newest run/event/PR link.
    This avoids turning the runtime manifest's regular poll into an unbounded
    event or artifact-log read.
    """
    ba.init_db(db_path)
    conn = bq.connect(db_path)
    try:
        initiative_rows = conn.execute(
            """
            SELECT id, title, state, pause_reason, created_at, updated_at
            FROM initiatives
            ORDER BY created_at ASC, id ASC
            """
        ).fetchall()
        initiatives = [
            _initiative_projection(conn, initiative_row) for initiative_row in initiative_rows
        ]
        return {
            "schema_version": SCHEMA_VERSION,
            "queue": bq.queue_status(db_path=db_path),
            "initiatives": initiatives,
        }
    finally:
        conn.close()


def _initiative_projection(conn: sqlite3.Connection, initiative_row: sqlite3.Row) -> dict[str, Any]:
    packet_rows = conn.execute(
        """
        SELECT p.packet_id, p.seq, p.title, p.depends_on_json, p.policy_json,
               p.base_sha, p.task_id, t.state AS task_state, t.blocked_reason,
               t.last_error, t.updated_at AS task_updated_at
        FROM initiative_packets p
        LEFT JOIN tasks t ON t.id = p.task_id
        WHERE p.initiative_id = ?
        ORDER BY p.seq ASC, p.packet_id ASC
        """,
        (initiative_row["id"],),
    ).fetchall()

    packet_models = [_packet_model(conn, initiative_row["id"], row) for row in packet_rows]
    packet_by_id = {packet["packet_id"]: packet for packet in packet_models}
    for packet in packet_models:
        packet["eligibility"] = _eligibility(packet, packet_by_id)

    state = _initiative_state(initiative_row["state"], packet_models)
    counts = _initiative_counts(packet_models)
    next_packet = next(
        (
            packet["packet_id"]
            for packet in packet_models
            if packet["eligibility"]["state"] == "eligible"
        ),
        None,
    )
    return {
        "initiative_id": initiative_row["id"],
        "title": initiative_row["title"],
        "state": state,
        "pause_reason": _safe_message(initiative_row["pause_reason"]),
        "next_packet": next_packet,
        "counts": counts,
        "created_at": initiative_row["created_at"],
        "updated_at": initiative_row["updated_at"],
        "packets": packet_models,
    }


def _packet_model(conn: sqlite3.Connection, initiative_id: str, row: sqlite3.Row) -> dict[str, Any]:
    depends_on = _decode_list(row["depends_on_json"], "initiative packet dependencies")
    policy = _decode_object(row["policy_json"], "initiative packet policy") or {}
    max_attempts = _max_attempts(policy)
    attempt_rows = conn.execute(
        """
        SELECT id, attempt_no, implementation_json, validation_json, review_json,
               outcome, lease_id, created_at, updated_at
        FROM packet_attempts
        WHERE initiative_id = ? AND packet_id = ?
        ORDER BY attempt_no DESC
        LIMIT 2
        """,
        (initiative_id, row["packet_id"]),
    ).fetchall()
    budget_row = conn.execute(
        """
        SELECT
            SUM(CASE WHEN outcome IN ('failed', 'aborted') THEN 1 ELSE 0 END) AS used,
            SUM(CASE WHEN outcome = 'succeeded' THEN 1 ELSE 0 END) AS succeeded
        FROM packet_attempts
        WHERE initiative_id = ? AND packet_id = ?
        """,
        (initiative_id, row["packet_id"]),
    ).fetchone()
    used = int(budget_row["used"] or 0)
    succeeded = int(budget_row["succeeded"] or 0)
    exhausted = succeeded == 0 and used >= max_attempts

    attempt = _attempt_projection(attempt_rows[0]) if attempt_rows else None
    previous_attempt = _attempt_projection(attempt_rows[1]) if len(attempt_rows) > 1 else None
    lease = _lease_projection(conn, row["packet_id"])
    run, run_infrastructure_failure = _run_projection(conn, row["task_id"])
    last_event = _event_projection(conn, row["task_id"])
    failure_kind = _failure_kind(
        task_state=row["task_state"],
        exhausted=exhausted,
        attempt=attempt,
        run=run,
        run_infrastructure_failure=run_infrastructure_failure,
        last_event=last_event,
    )

    return {
        "packet_id": row["packet_id"],
        "title": row["title"],
        "task_id": row["task_id"],
        "task_state": row["task_state"],
        "depends_on": depends_on,
        "eligibility": None,
        "budget": {"used": used, "max": max_attempts, "exhausted": exhausted},
        "attempt": attempt,
        "previous_attempt": previous_attempt,
        "lease": lease,
        "run": run,
        "publication": _publication_projection(conn, row["task_id"]),
        "last_event": last_event,
        "failure_kind": failure_kind,
        "blocked_reason": _safe_message(row["blocked_reason"]),
        "last_error": _safe_message(row["last_error"]),
        "updated_at": row["task_updated_at"],
        "base_sha": row["base_sha"],
    }


def _attempt_projection(row: sqlite3.Row) -> dict[str, Any]:
    implementation = _decode_object(row["implementation_json"], "attempt implementation")
    validation = _decode_object(row["validation_json"], "attempt validation")
    review = _decode_object(row["review_json"], "attempt review")
    implementation_status = _known_string(implementation, "status")
    validation_status = _known_string(validation, "status")
    review_verdict = _known_string(review, "verdict")
    return {
        "id": row["id"],
        "number": row["attempt_no"],
        "outcome": row["outcome"],
        "implementation_status": implementation_status,
        "validation_status": validation_status,
        "review_verdict": review_verdict,
        "lease_id": row["lease_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _lease_projection(conn: sqlite3.Connection, packet_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT lease_id, worker_id, branch, base_sha, created_at
        FROM branch_leases
        WHERE packet_id = ?
        """,
        (packet_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row["lease_id"],
        "worker_id": row["worker_id"],
        "branch": row["branch"],
        "base_sha": row["base_sha"],
        "created_at": row["created_at"],
    }


def _run_projection(conn: sqlite3.Connection, task_id: str) -> tuple[dict[str, Any] | None, bool]:
    row = conn.execute(
        """
        SELECT id, state, started_at, last_heartbeat_at, ended_at, exit_code,
               final_report_json
        FROM runs
        WHERE task_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (task_id,),
    ).fetchone()
    if row is None:
        return None, False
    report = _decode_object(row["final_report_json"], "run final report")
    infrastructure_failure = bool(report and report.get("worker_started") is False)
    return (
        {
            "id": row["id"],
            "state": row["state"],
            "started_at": row["started_at"],
            "last_heartbeat_at": row["last_heartbeat_at"],
            "ended_at": row["ended_at"],
            "exit_code": row["exit_code"],
        },
        infrastructure_failure,
    )


def _publication_projection(conn: sqlite3.Connection, task_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT pr_url, checks_state, review_state, merged
        FROM pr_links
        WHERE task_id = ?
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
        (task_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "pr_url": row["pr_url"],
        "checks_state": row["checks_state"],
        "review_state": row["review_state"],
        "merged": bool(row["merged"]),
    }


def _event_projection(conn: sqlite3.Connection, task_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT id, type, payload_json, created_at
        FROM events
        WHERE task_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (task_id,),
    ).fetchone()
    if row is None:
        return None
    payload = _decode_object(row["payload_json"], "Builder event payload") or {}
    reason = _event_reason(payload)
    counts_toward_budget = payload.get("counts_toward_budget")
    return {
        "id": row["id"],
        "type": row["type"],
        "created_at": row["created_at"],
        "reason": reason,
        "counts_toward_budget": counts_toward_budget
        if isinstance(counts_toward_budget, bool)
        else None,
    }


def _eligibility(packet: dict[str, Any], packet_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    task_state = packet["task_state"]
    if task_state is None:
        return {"state": "unavailable", "blocked_by": []}
    if packet["budget"]["exhausted"]:
        return {"state": "blocked", "blocked_by": [packet["packet_id"]]}
    if task_state != bq.QUEUED:
        return {"state": "not_queued", "blocked_by": []}

    blocked_by: list[str] = []
    waiting_on: list[str] = []
    for dependency_id in packet["depends_on"]:
        dependency = packet_by_id.get(dependency_id)
        if dependency is None:
            blocked_by.append(dependency_id)
            continue
        if dependency["budget"]["exhausted"] or dependency["task_state"] in {
            bq.BLOCKED,
            bq.FAILED,
            bq.CANCELLED,
        }:
            blocked_by.append(dependency_id)
        elif dependency["task_state"] != bq.DONE:
            waiting_on.append(dependency_id)
    if blocked_by:
        return {"state": "blocked", "blocked_by": blocked_by}
    if waiting_on:
        return {"state": "waiting", "blocked_by": waiting_on}
    return {"state": "eligible", "blocked_by": []}


def _initiative_state(stored_state: str, packets: list[dict[str, Any]]) -> str:
    if stored_state == bi.INITIATIVE_PAUSED:
        return bi.INITIATIVE_PAUSED
    if packets and all(packet["task_state"] == bq.DONE for packet in packets):
        return bi.INITIATIVE_COMPLETED
    if any(
        packet["task_state"] in {bq.BLOCKED, bq.FAILED, bq.CANCELLED}
        or packet["budget"]["exhausted"]
        or packet["eligibility"]["state"] == "blocked"
        for packet in packets
    ):
        return bi.INITIATIVE_FAILED
    if any(packet["eligibility"]["state"] == "eligible" for packet in packets):
        return bi.INITIATIVE_ACTIVE
    return bi.INITIATIVE_PAUSED


def _initiative_counts(packets: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "total": len(packets),
        "queued": 0,
        "claimed": 0,
        "running": 0,
        "blocked": 0,
        "pr_opened": 0,
        "awaiting_review": 0,
        "done": 0,
        "failed": 0,
        "cancelled": 0,
        "exhausted": 0,
    }
    for packet in packets:
        task_state = packet["task_state"]
        if task_state in counts:
            counts[task_state] += 1
        if packet["budget"]["exhausted"]:
            counts["exhausted"] += 1
    return counts


def _failure_kind(
    *,
    task_state: str | None,
    exhausted: bool,
    attempt: dict[str, Any] | None,
    run: dict[str, Any] | None,
    run_infrastructure_failure: bool,
    last_event: dict[str, Any] | None,
) -> str | None:
    if task_state == bq.CANCELLED:
        return "cancelled"
    if exhausted:
        return "exhausted"
    if run and run["state"] in _IDENTITY_RUN_STATES:
        return "identity"
    if run_infrastructure_failure:
        return "infrastructure"
    if last_event and last_event["type"] == "infrastructure_failed":
        return "infrastructure"
    if attempt is None:
        return None
    if attempt["outcome"] == ba.ATTEMPT_CRASHED:
        return "infrastructure"
    if attempt["validation_status"] == ba.VALIDATION_FAILED:
        return "validation"
    if attempt["review_verdict"] in {"reject", "request_changes"}:
        return "review"
    if attempt["implementation_status"] in {"failed", "aborted"} or task_state == bq.FAILED:
        return "implementation"
    return None


def _max_attempts(policy: dict[str, Any]) -> int:
    value = policy.get("max_attempts", ba.DEFAULT_MAX_ATTEMPTS)
    if isinstance(value, int) and value >= 1:
        return value
    return ba.DEFAULT_MAX_ATTEMPTS


def _decode_object(raw: Any, label: str) -> dict[str, Any] | None:
    if raw is None:
        return None
    parsed = _decode_json(raw, label)
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} must be a JSON object")
    return parsed


def _decode_list(raw: Any, label: str) -> list[str]:
    if raw is None:
        return []
    parsed = _decode_json(raw, label)
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError(f"{label} must be a JSON string list")
    return parsed


def _decode_json(raw: Any, label: str) -> Any:
    if not isinstance(raw, str):
        raise ValueError(f"{label} is not serialized as JSON text")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} contains invalid JSON: {exc}") from exc


def _known_string(value: dict[str, Any] | None, key: str) -> str | None:
    if value is None:
        return None
    candidate = value.get(key)
    return candidate if isinstance(candidate, str) else None


def _event_reason(payload: dict[str, Any]) -> str | None:
    for key in ("reason", "message", "error"):
        value = payload.get(key)
        if isinstance(value, str):
            return _safe_message(value)
    return None


def _safe_message(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = " ".join(value.split())
    redacted = _PATH_PATTERN.sub("[path]", normalized)
    if len(redacted) <= _MESSAGE_CAP:
        return redacted
    return f"{redacted[:_MESSAGE_CAP - 1]}…"
