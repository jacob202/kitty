"""Bounded, read-only Builder status projection for the Kitty runtime API.

The client receives a fixed-size investigation view over Builder's durable
tables. Task, attempt, run, lease, initiative, and publication lifecycles stay
owned by their existing modules; this file only reads and safely projects them.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from gateway import builder_attempt as ba
from gateway import builder_initiative as bi
from gateway import builder_queue as bq

SCHEMA_VERSION = 2
ATTEMPT_HISTORY_LIMIT = 10
REVIEW_FINDING_LIMIT = 5
SNAPSHOT_QUERY_COUNT = 8
_MESSAGE_CAP = 500
_OBJECTIVE_CAP = 1200
_PATH_PATTERN = re.compile(r"(?<![A-Za-z0-9_])/(?:[^\s/]+/)+[^\s/]+")
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|token|secret|password|authorization)"
    r"\b\s*[:=]\s*(?:bearer\s+)?[^\s,;]+"
)
_TOKEN_PATTERN = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{8,}|"
    r"github_pat_[A-Za-z0-9_]{8,}|xox[baprs]-[A-Za-z0-9-]{8,})\b"
)
_GITHUB_PR_PATH_PATTERN = re.compile(
    r"^/[^/?#]+/[^/?#]+/pull/[1-9][0-9]*/?$"
)

_INVESTIGATION_AVAILABILITY = {
    "logs": {
        "state": "unavailable",
        "reason": "Safe bounded log delivery is not available yet.",
    },
    "artifacts": {
        "state": "unavailable",
        "reason": "Safe durable artifact delivery is not available yet.",
    },
}

PacketKey = tuple[str, str]


def build_status_snapshot(*, db_path: Path | None = None) -> dict[str, Any]:
    """Return a deterministic snapshot with a fixed SQL query budget.

    Attempt history is capped per packet. All other packet relationships use
    one bulk query each, so manifest polling does not grow into an N+1 query
    pattern as initiatives gain packets.
    """
    ba.init_db(db_path)
    conn = bq.connect(db_path)
    try:
        initiative_rows = _read_initiatives(conn)
        packet_rows = _read_packets(conn)
        attempts = _group_attempts(_read_attempts(conn))
        leases = _index_rows(_read_leases(conn), "initiative_id", "packet_id")
        runs = _index_rows(_read_latest_runs(conn), "task_id")
        publications = _index_rows(_read_latest_publications(conn), "task_id")
        events = _index_rows(_read_latest_events(conn), "task_id")

        packet_models: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in packet_rows:
            key = (str(row["initiative_id"]), str(row["packet_id"]))
            packet_models[key[0]].append(
                _packet_model(
                    row,
                    attempt_rows=attempts.get(key, []),
                    lease_row=leases.get(key),
                    run_row=runs.get(str(row["task_id"])),
                    publication_row=publications.get(str(row["task_id"])),
                    event_row=events.get(str(row["task_id"])),
                )
            )

        initiatives = [
            _initiative_projection(row, packet_models.get(str(row["id"]), []))
            for row in initiative_rows
        ]
        all_packets = [
            packet
            for initiative in initiatives
            for packet in initiative["packets"]
        ]
        partial_packets = sum(
            packet["data_quality"]["state"] != "complete"
            for packet in all_packets
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "attempt_history_limit": ATTEMPT_HISTORY_LIMIT,
            "integrity": {
                "state": "partial" if partial_packets else "complete",
                "partial_packets": partial_packets,
                "total_packets": len(all_packets),
            },
            "queue": _queue_projection(conn),
            "initiatives": initiatives,
        }
    finally:
        conn.close()


def _read_initiatives(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, title, state, pause_reason, created_at, updated_at
        FROM initiatives
        ORDER BY created_at ASC, id ASC
        """
    ).fetchall()


def _read_packets(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT p.initiative_id, p.packet_id, p.seq, p.title, p.objective,
               p.depends_on_json, p.policy_json, p.base_sha, p.task_id,
               t.state AS task_state, t.blocked_reason, t.last_error,
               t.updated_at AS task_updated_at
        FROM initiative_packets p
        LEFT JOIN tasks t ON t.id = p.task_id
        ORDER BY p.initiative_id ASC, p.seq ASC, p.packet_id ASC
        """
    ).fetchall()


def _read_attempts(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        WITH ranked AS (
            SELECT a.id, a.initiative_id, a.packet_id, a.attempt_no,
                   a.implementation_json, a.validation_json, a.review_json,
                   a.outcome, a.lease_id, a.created_at, a.updated_at,
                   ROW_NUMBER() OVER (
                       PARTITION BY a.initiative_id, a.packet_id
                       ORDER BY a.attempt_no DESC, a.id DESC
                   ) AS history_rank,
                   COUNT(*) OVER (
                       PARTITION BY a.initiative_id, a.packet_id
                   ) AS attempt_count,
                   SUM(CASE WHEN a.outcome IN ('failed', 'aborted') THEN 1 ELSE 0 END)
                       OVER (PARTITION BY a.initiative_id, a.packet_id) AS budget_used,
                   SUM(CASE WHEN a.outcome = 'succeeded' THEN 1 ELSE 0 END)
                       OVER (PARTITION BY a.initiative_id, a.packet_id) AS succeeded_count
            FROM packet_attempts a
            INNER JOIN initiative_packets p
                ON p.initiative_id = a.initiative_id
               AND p.packet_id = a.packet_id
        )
        SELECT * FROM ranked
        WHERE history_rank <= ?
        ORDER BY initiative_id ASC, packet_id ASC, attempt_no DESC, id DESC
        """,
        (ATTEMPT_HISTORY_LIMIT,),
    ).fetchall()


def _read_leases(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        WITH ranked AS (
            SELECT a.initiative_id, a.packet_id, l.lease_id, l.worker_id,
                   l.branch, l.base_sha, l.created_at,
                   ROW_NUMBER() OVER (
                       PARTITION BY a.initiative_id, a.packet_id
                       ORDER BY a.attempt_no DESC, a.id DESC
                   ) AS row_rank
            FROM packet_attempts a
            INNER JOIN branch_leases l ON l.lease_id = a.lease_id
            WHERE a.outcome IS NULL
        )
        SELECT initiative_id, packet_id, lease_id, worker_id, branch,
               base_sha, created_at
        FROM ranked
        WHERE row_rank = 1
        ORDER BY initiative_id ASC, packet_id ASC
        """
    ).fetchall()


def _read_latest_runs(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        WITH ranked AS (
            SELECT r.id, r.task_id, r.state, r.started_at,
                   r.last_heartbeat_at, r.ended_at, r.exit_code,
                   r.final_report_json, r.created_at, r.updated_at,
                   ROW_NUMBER() OVER (
                       PARTITION BY r.task_id
                       ORDER BY r.created_at DESC, r.id DESC
                   ) AS row_rank
            FROM runs r
            INNER JOIN initiative_packets p ON p.task_id = r.task_id
        )
        SELECT * FROM ranked
        WHERE row_rank = 1
        ORDER BY task_id ASC
        """
    ).fetchall()


def _read_latest_publications(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        WITH ranked AS (
            SELECT pr.id, pr.task_id, pr.pr_number, pr.pr_url, pr.head_sha,
                   pr.checks_state, pr.review_state, pr.merged, pr.merged_at,
                   pr.updated_at,
                   ROW_NUMBER() OVER (
                       PARTITION BY pr.task_id
                       ORDER BY pr.updated_at DESC, pr.id DESC
                   ) AS row_rank
            FROM pr_links pr
            INNER JOIN initiative_packets p ON p.task_id = pr.task_id
        )
        SELECT * FROM ranked
        WHERE row_rank = 1
        ORDER BY task_id ASC
        """
    ).fetchall()


def _read_latest_events(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        WITH ranked AS (
            SELECT e.id, e.task_id, e.type, e.payload_json, e.created_at,
                   ROW_NUMBER() OVER (
                       PARTITION BY e.task_id
                       ORDER BY e.id DESC
                   ) AS row_rank
            FROM events e
            INNER JOIN initiative_packets p ON p.task_id = e.task_id
        )
        SELECT * FROM ranked
        WHERE row_rank = 1
        ORDER BY task_id ASC
        """
    ).fetchall()


def _group_attempts(rows: list[sqlite3.Row]) -> dict[PacketKey, list[sqlite3.Row]]:
    grouped: dict[PacketKey, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["initiative_id"]), str(row["packet_id"]))].append(row)
    return dict(grouped)


def _index_rows(
    rows: list[sqlite3.Row], *keys: str
) -> dict[Any, sqlite3.Row]:
    indexed: dict[Any, sqlite3.Row] = {}
    for row in rows:
        key: Any
        if len(keys) == 1:
            key = str(row[keys[0]])
        else:
            key = tuple(str(row[column]) for column in keys)
        indexed[key] = row
    return indexed


def _initiative_projection(
    initiative_row: sqlite3.Row,
    packets: list[dict[str, Any]],
) -> dict[str, Any]:
    task_states = {
        packet["packet_id"]: packet["task_state"]
        for packet in packets
    }
    exhausted_ids = {
        packet["packet_id"]
        for packet in packets
        if packet["budget"]["exhausted"] is True
    }
    for packet in packets:
        packet["eligibility"] = bi.derive_packet_eligibility(
            packet_id=packet["packet_id"],
            task_state=packet["task_state"],
            depends_on=packet["depends_on"],
            task_states=task_states,
            exhausted_packet_ids=exhausted_ids,
            data_available=packet.pop("_eligibility_data_available"),
        )

    counts = _initiative_counts(packets)
    eligible_packets = [
        packet
        for packet in packets
        if packet["eligibility"]["state"] == "eligible"
    ]
    state = bi.derive_initiative_state(
        stored_state=str(initiative_row["state"]),
        total_packets=len(packets),
        done_count=counts["done"],
        has_blocked=any(
            packet["eligibility"]["state"] == "blocked"
            for packet in packets
        ),
        has_failed=bool(counts["failed"] or counts["cancelled"]),
        has_exhausted=bool(counts["exhausted"]),
        has_eligible=bool(eligible_packets),
    )
    partial_packets = sum(
        packet["data_quality"]["state"] != "complete"
        for packet in packets
    )
    return {
        "initiative_id": initiative_row["id"],
        "title": initiative_row["title"],
        "state": state,
        "pause_reason": _safe_message(initiative_row["pause_reason"]),
        "next_packet": (
            eligible_packets[0]["packet_id"] if eligible_packets else None
        ),
        "counts": counts,
        "data_quality": {
            "state": "partial" if partial_packets else "complete",
            "partial_packets": partial_packets,
        },
        "created_at": initiative_row["created_at"],
        "updated_at": initiative_row["updated_at"],
        "packets": packets,
    }


def _packet_model(
    row: sqlite3.Row,
    *,
    attempt_rows: list[sqlite3.Row],
    lease_row: sqlite3.Row | None,
    run_row: sqlite3.Row | None,
    publication_row: sqlite3.Row | None,
    event_row: sqlite3.Row | None,
) -> dict[str, Any]:
    issues: list[str] = []
    depends_on, dependency_issue = _decode_string_list(
        row["depends_on_json"], "packet dependencies"
    )
    if dependency_issue:
        issues.append(dependency_issue)
    policy, policy_issue = _decode_optional_object(
        row["policy_json"], "packet policy"
    )
    if policy_issue:
        issues.append(policy_issue)

    attempt_history: list[dict[str, Any]] = []
    for attempt_row in attempt_rows:
        attempt, attempt_issues = _attempt_projection(attempt_row)
        attempt_history.append(attempt)
        issues.extend(attempt_issues)

    attempt_count = int(attempt_rows[0]["attempt_count"]) if attempt_rows else 0
    used = int(attempt_rows[0]["budget_used"] or 0) if attempt_rows else 0
    succeeded = (
        int(attempt_rows[0]["succeeded_count"] or 0) if attempt_rows else 0
    )
    max_attempts = _max_attempts(policy, issues)
    exhausted = (
        None
        if max_attempts is None
        else succeeded == 0 and used >= max_attempts
    )

    lease = _lease_projection(lease_row)
    run, run_infrastructure_failure, run_issues = _run_projection(run_row)
    issues.extend(run_issues)
    publication, publication_issues = _publication_projection(publication_row)
    issues.extend(publication_issues)
    last_event, event_issues = _event_projection(event_row)
    issues.extend(event_issues)

    if row["task_state"] is None:
        issues.append("task record is missing")
    latest_attempt = attempt_history[0] if attempt_history else None
    failure_kind = _failure_kind(
        task_state=row["task_state"],
        exhausted=exhausted is True,
        attempt=latest_attempt,
        run=run,
        run_infrastructure_failure=run_infrastructure_failure,
        last_event=last_event,
    )
    unique_issues = list(dict.fromkeys(issues))
    return {
        "initiative_id": row["initiative_id"],
        "packet_id": row["packet_id"],
        "title": row["title"],
        "objective": _safe_message(row["objective"], cap=_OBJECTIVE_CAP),
        "task_id": row["task_id"],
        "task_state": row["task_state"],
        "depends_on": depends_on,
        "eligibility": None,
        "_eligibility_data_available": (
            dependency_issue is None and row["task_state"] is not None
        ),
        "budget": {
            "used": used,
            "max": max_attempts,
            "exhausted": exhausted,
        },
        "attempt_count": attempt_count,
        "attempt_history_truncated": attempt_count > len(attempt_history),
        "attempt_history": attempt_history,
        "lease": lease,
        "run": run,
        "publication": publication,
        "last_event": last_event,
        "failure_kind": failure_kind,
        "blocked_reason": _safe_message(row["blocked_reason"]),
        "last_error": _safe_message(row["last_error"]),
        "updated_at": row["task_updated_at"],
        "base_sha": _safe_sha(row["base_sha"]),
        "data_quality": {
            "state": "partial" if unique_issues else "complete",
            "issues": unique_issues,
        },
        "investigation": {
            key: dict(value)
            for key, value in _INVESTIGATION_AVAILABILITY.items()
        },
    }


def _attempt_projection(
    row: sqlite3.Row,
) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    implementation, implementation_issue = _decode_optional_object(
        row["implementation_json"], "implementation evidence"
    )
    validation, validation_issue = _decode_optional_object(
        row["validation_json"], "validation evidence"
    )
    review, review_issue = _decode_optional_object(
        row["review_json"], "review evidence"
    )
    issues.extend(
        issue
        for issue in (implementation_issue, validation_issue, review_issue)
        if issue
    )

    implementation_status = _known_string(implementation, "status")
    implementation_projection = None
    if implementation is not None:
        implementation_projection = {
            "status": implementation_status,
            "summary": _safe_message(implementation.get("summary")),
            "diff_summary": _safe_message(implementation.get("diff_summary")),
        }

    validation_projection, validation_projection_issues = _validation_projection(
        validation
    )
    issues.extend(validation_projection_issues)
    review_projection, review_projection_issues = _review_projection(review)
    issues.extend(review_projection_issues)
    unique_issues = list(dict.fromkeys(issues))
    outcome = row["outcome"]
    return (
        {
            "id": row["id"],
            "number": row["attempt_no"],
            "outcome": outcome,
            "counts_toward_budget": outcome in ba._BUDGET_CONSUMING_OUTCOMES,
            "implementation_status": implementation_status,
            "validation_status": (
                validation_projection["status"]
                if validation_projection is not None
                else None
            ),
            "review_verdict": (
                review_projection["verdict"]
                if review_projection is not None
                else None
            ),
            "implementation": implementation_projection,
            "validation": validation_projection,
            "review": review_projection,
            "lease_id": row["lease_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "data_quality": {
                "state": "partial" if unique_issues else "complete",
                "issues": unique_issues,
            },
        },
        unique_issues,
    )


def _validation_projection(
    validation: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    if validation is None:
        return None, []
    issues: list[str] = []
    status = _known_string(validation, "status")
    raw_commands = validation.get("commands")
    if not isinstance(raw_commands, list):
        issues.append("validation command evidence is malformed")
        commands: list[dict[str, Any]] = []
    else:
        commands = [command for command in raw_commands if isinstance(command, dict)]
        if len(commands) != len(raw_commands):
            issues.append("validation command evidence is malformed")
    failed_commands = [command for command in commands if command.get("passed") is False]
    return (
        {
            "status": status,
            "command_count": len(commands),
            "failed_command_count": len(failed_commands),
            "summary": _validation_summary(status, commands, failed_commands),
        },
        issues,
    )


def _validation_summary(
    status: str | None,
    commands: list[dict[str, Any]],
    failed_commands: list[dict[str, Any]],
) -> str:
    if status == ba.VALIDATION_SKIPPED:
        return "No deterministic validation commands were declared."
    if status == ba.VALIDATION_PASSED:
        count = len(commands)
        noun = "command" if count == 1 else "commands"
        return f"{count} validation {noun} passed."
    if status == ba.VALIDATION_FAILED:
        count = len(failed_commands)
        noun = "command" if count == 1 else "commands"
        first = failed_commands[0] if failed_commands else {}
        exit_code = first.get("exit_code")
        detail = "timeout" if exit_code is None else f"exit {exit_code}"
        return f"{count} validation {noun} failed ({detail})."
    return "Validation evidence has an unknown status."


def _review_projection(
    review: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    if review is None:
        return None, []
    issues: list[str] = []
    raw_findings = review.get("findings") or []
    if not isinstance(raw_findings, list):
        issues.append("review findings are malformed")
        raw_findings = []
    findings: list[dict[str, str | None]] = []
    for finding in raw_findings[:REVIEW_FINDING_LIMIT]:
        if not isinstance(finding, dict):
            issues.append("review findings are malformed")
            continue
        findings.append(
            {
                "severity": _known_string(finding, "severity"),
                "note": _safe_message(finding.get("note")),
            }
        )
    return (
        {
            "verdict": _known_string(review, "verdict"),
            "summary": _safe_message(review.get("summary")),
            "findings": findings,
            "findings_truncated": len(raw_findings) > REVIEW_FINDING_LIMIT,
        },
        issues,
    )


def _lease_projection(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row["lease_id"],
        "worker_id": _safe_message(row["worker_id"], cap=160),
        "branch": _safe_message(row["branch"], cap=240),
        "base_sha": _safe_sha(row["base_sha"]),
        "created_at": row["created_at"],
    }


def _run_projection(
    row: sqlite3.Row | None,
) -> tuple[dict[str, Any] | None, bool, list[str]]:
    if row is None:
        return None, False, []
    report, issue = _decode_optional_object(
        row["final_report_json"], "run final report"
    )
    issues = [issue] if issue else []
    infrastructure_failure = bool(report and report.get("worker_started") is False)
    return (
        {
            "id": row["id"],
            "state": row["state"],
            "started_at": row["started_at"],
            "last_heartbeat_at": row["last_heartbeat_at"],
            "ended_at": row["ended_at"],
            "exit_code": row["exit_code"],
            "updated_at": row["updated_at"],
        },
        infrastructure_failure,
        issues,
    )


def _publication_projection(
    row: sqlite3.Row | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    if row is None:
        return None, []
    issues: list[str] = []
    pr_url = _safe_github_url(row["pr_url"])
    if row["pr_url"] and pr_url is None:
        issues.append("publication URL is not a safe GitHub HTTPS link")
    head_sha = _safe_sha(row["head_sha"])
    if row["head_sha"] and head_sha is None:
        issues.append("publication head SHA is malformed")
    return (
        {
            "pr_number": row["pr_number"],
            "pr_url": pr_url,
            "head_sha": head_sha,
            "checks_state": _safe_message(row["checks_state"], cap=120),
            "review_state": _safe_message(row["review_state"], cap=120),
            "merged": bool(row["merged"]),
            "merged_at": row["merged_at"],
            "updated_at": row["updated_at"],
        },
        issues,
    )


def _event_projection(
    row: sqlite3.Row | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    if row is None:
        return None, []
    payload, issue = _decode_optional_object(row["payload_json"], "event payload")
    reason = _event_reason(payload or {})
    counts_toward_budget = (payload or {}).get("counts_toward_budget")
    return (
        {
            "id": row["id"],
            "type": row["type"],
            "created_at": row["created_at"],
            "reason": reason,
            "counts_toward_budget": (
                counts_toward_budget
                if isinstance(counts_toward_budget, bool)
                else None
            ),
        },
        [issue] if issue else [],
    )


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
        if packet["budget"]["exhausted"] is True:
            counts["exhausted"] += 1
    return counts


def _queue_projection(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT state, COUNT(*) AS count
        FROM tasks
        WHERE archived_at IS NULL
        GROUP BY state
        ORDER BY state ASC
        """
    ).fetchall()
    per_state = {str(row["state"]): int(row["count"]) for row in rows}
    return {
        "total": sum(per_state.values()),
        "queued": per_state.get(bq.QUEUED, 0),
        "claimed": per_state.get(bq.CLAIMED, 0),
        "running": per_state.get(bq.RUNNING, 0),
        "blocked": per_state.get(bq.BLOCKED, 0),
        "pr_opened": per_state.get(bq.PR_OPENED, 0),
        "awaiting_review": per_state.get(bq.AWAITING_REVIEW, 0),
        "done": per_state.get(bq.DONE, 0),
        "failed": per_state.get(bq.FAILED, 0),
        "cancelled": per_state.get(bq.CANCELLED, 0),
    }


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
    run_state = run.get("state") if run else None
    if run_state == bq.RUN_SCOPE_VIOLATION:
        return "scope"
    if run_state == bq.RUN_LEASE_LOST:
        return "identity"
    event_type = last_event.get("type") if last_event else None
    if event_type in {"scope_violation", "run_scope_violation"}:
        return "scope"
    if event_type in {"identity_failed", "run_lease_lost"}:
        return "identity"
    if run_infrastructure_failure or event_type == "infrastructure_failed":
        return "infrastructure"
    if attempt is not None:
        if attempt.get("outcome") == ba.ATTEMPT_CRASHED:
            return "infrastructure"
        validation_status = attempt.get("validation_status")
        if validation_status is None and isinstance(attempt.get("validation"), dict):
            validation_status = attempt["validation"].get("status")
        if validation_status == ba.VALIDATION_FAILED:
            return "validation"
        review_verdict = attempt.get("review_verdict")
        if review_verdict is None and isinstance(attempt.get("review"), dict):
            review_verdict = attempt["review"].get("verdict")
        if review_verdict in {"reject", "request_changes"}:
            return "review"
        implementation_status = attempt.get("implementation_status")
        if implementation_status is None and isinstance(
            attempt.get("implementation"), dict
        ):
            implementation_status = attempt["implementation"].get("status")
        if implementation_status in {"failed", "aborted"}:
            return "implementation"
    if task_state == bq.FAILED or event_type in {"worker_failed", "run_failed"}:
        return "implementation"
    if task_state == bq.BLOCKED:
        return "blocked"
    return None


def _max_attempts(
    policy: dict[str, Any] | None,
    issues: list[str],
) -> int | None:
    if policy is None:
        issues.append("attempt budget is unavailable because packet policy is malformed")
        return None
    value = policy.get("max_attempts", ba.DEFAULT_MAX_ATTEMPTS)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
        return value
    issues.append("packet max_attempts is malformed")
    return None


def _decode_optional_object(
    raw: Any,
    label: str,
) -> tuple[dict[str, Any] | None, str | None]:
    if raw is None:
        return None, None
    if not isinstance(raw, str):
        return None, f"{label} is malformed"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None, f"{label} is malformed"
    if not isinstance(parsed, dict):
        return None, f"{label} is malformed"
    return parsed, None


def _decode_string_list(
    raw: Any,
    label: str,
) -> tuple[list[str], str | None]:
    if raw is None:
        return [], None
    if not isinstance(raw, str):
        return [], f"{label} are malformed"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return [], f"{label} are malformed"
    if not isinstance(parsed, list) or not all(
        isinstance(item, str) for item in parsed
    ):
        return [], f"{label} are malformed"
    return parsed, None


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


def _safe_sha(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if len(normalized) != 40 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        return None
    return normalized


def _safe_github_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value.strip())
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or _GITHUB_PR_PATH_PATTERN.fullmatch(parsed.path) is None
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    return value.strip()


def _safe_message(value: Any, *, cap: int = _MESSAGE_CAP) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = " ".join(value.split())
    redacted = _SECRET_ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}=[redacted]",
        normalized,
    )
    redacted = _TOKEN_PATTERN.sub("[secret]", redacted)
    redacted = _PATH_PATTERN.sub("[path]", redacted)
    if len(redacted) <= cap:
        return redacted
    return f"{redacted[:cap - 1]}…"
