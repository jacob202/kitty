"""Work spine — read-only projection over public Builder read APIs.

Provides a stable ``WorkItem`` view of Builder queue state using the
``builder:<task_id>`` identity scheme. No new Work database: every query
delegates to the public read surfaces of the Builder modules.

Builder is the only v1 source of truth.  Every item has ``source`` equal
to ``"builder"`` and ``source_id`` equal to the Builder task id.

Known Builder task states map to normalized Work states.  An unknown task
state from the Builder store raises ``WorkStateError`` immediately — no
silent defaulting to ``unknown``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from gateway import builder_attempt as ba
from gateway import builder_queue as bq
from gateway.builder_queue_db import TaskNotFoundError

logger = logging.getLogger("kitty.work_spine")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WORK_ID_PREFIX = "builder:"

# Normalized Work states — the public contract.
# queued/claimed → pending; awaiting_review/pr_opened → review.
WORK_STATE_PENDING = "pending"
WORK_STATE_RUNNING = "running"
WORK_STATE_BLOCKED = "blocked"
WORK_STATE_REVIEW = "review"
WORK_STATE_COMPLETED = "completed"
WORK_STATE_FAILED = "failed"
WORK_STATE_CANCELLED = "cancelled"

_WORK_STATES = frozenset({
    WORK_STATE_PENDING,
    WORK_STATE_RUNNING,
    WORK_STATE_BLOCKED,
    WORK_STATE_REVIEW,
    WORK_STATE_COMPLETED,
    WORK_STATE_FAILED,
    WORK_STATE_CANCELLED,
})

# Builder source label — the only valid source in v1.
SOURCE_BUILDER = "builder"

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class WorkError(RuntimeError):
    """Base error for work spine operations."""


class WorkNotFoundError(WorkError):
    """Raised when a work ID does not correspond to any known Builder work."""


class WorkStateError(WorkError):
    """Raised when the Builder store returns an unrecognised task state."""


class WorkSourceError(WorkError):
    """Raised when a work ID has an unrecognised source prefix."""


# ---------------------------------------------------------------------------
# State mapping
# ---------------------------------------------------------------------------

_BUILDER_TO_WORK_STATE: dict[str, str] = {
    bq.QUEUED: WORK_STATE_PENDING,
    bq.CLAIMED: WORK_STATE_PENDING,
    bq.RUNNING: WORK_STATE_RUNNING,
    bq.BLOCKED: WORK_STATE_BLOCKED,
    bq.AWAITING_REVIEW: WORK_STATE_REVIEW,
    bq.PR_OPENED: WORK_STATE_REVIEW,
    bq.DONE: WORK_STATE_COMPLETED,
    bq.FAILED: WORK_STATE_FAILED,
    bq.CANCELLED: WORK_STATE_CANCELLED,
}


def _normalize_state(builder_state: str) -> str:
    """Map a Builder task state to the normalized Work state.

    Raises ``WorkStateError`` for any unrecognised value.
    """
    work_state = _BUILDER_TO_WORK_STATE.get(builder_state)
    if work_state is None:
        raise WorkStateError(
            f"unrecognised Builder task state {builder_state!r}; "
            f"known states: {sorted(_BUILDER_TO_WORK_STATE)}"
        )
    return work_state


# ---------------------------------------------------------------------------
# ID helpers
# ---------------------------------------------------------------------------


def _parse_work_id(work_id: str) -> tuple[str, str]:
    """Split a ``builder:<task_id>`` work ID into (source, task_id).

    Raises ``WorkSourceError`` if the prefix is not recognised.
    """
    if work_id.startswith(WORK_ID_PREFIX):
        return SOURCE_BUILDER, work_id[len(WORK_ID_PREFIX):]
    raise WorkSourceError(
        f"work ID {work_id!r} has unrecognised source prefix; "
        f"expected {WORK_ID_PREFIX!r}<task_id>"
    )


def _build_work_id(task_id: str) -> str:
    """Return a ``builder:<task_id>`` work ID for the given task."""
    return f"{WORK_ID_PREFIX}{task_id}"


# ---------------------------------------------------------------------------
# Projection: list work items
# ---------------------------------------------------------------------------


def list_work(
    state: str | None = None,
    source: str | None = None,
    limit: int = 100,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """List work items, optionally filtered.

    In v1 only ``source=builder`` is supported.  Any other source value
    raises ``WorkSourceError``.

    Args:
        state: Filter by normalized Work state.
        source: Must be ``"builder"`` in v1 (or ``None``).
        limit: Maximum items to return (clamped to 1-500).

    Returns:
        A list of work item dicts.

    Raises:
        WorkStateError: if *state* is not a recognised Work state.
        WorkSourceError: if *source* is not ``"builder"``.
    """
    # v1: only source=builder is valid.
    if source is not None and source != SOURCE_BUILDER:
        raise WorkSourceError(
            f"unsupported source {source!r}; only {SOURCE_BUILDER!r} is supported in v1"
        )

    if state is not None and state not in _WORK_STATES:
        raise WorkStateError(
            f"unrecognised Work state {state!r}; "
            f"valid: {sorted(_WORK_STATES)}"
        )

    # Map Work state back to Builder states for the query.
    # Multiple Builder states can map to one Work state (e.g. queued/claimed →
    # pending), so collect all matching Builder states and query each.
    builder_states: list[str] = []
    if state is not None:
        for bs, ws in _BUILDER_TO_WORK_STATE.items():
            if ws == state:
                builder_states.append(bs)
        if not builder_states:
            raise WorkStateError(
                f"cannot resolve Work state {state!r} to a Builder state"
            )

    if builder_states:
        tasks: list[dict[str, Any]] = []
        for bs in sorted(builder_states):
            tasks.extend(bq.list_tasks(state=bs, db_path=db_path))
    else:
        tasks = bq.list_tasks(db_path=db_path)

    # Clamp limit.
    if limit < 1:
        limit = 1
    elif limit > 500:
        limit = 500
    tasks = tasks[:limit]

    result: list[dict[str, Any]] = []
    for task in tasks:
        work_state = _normalize_state(task["state"])
        result.append(_task_to_list_item(task, work_state))

    return result


def _task_to_list_item(task: dict[str, Any], work_state: str) -> dict[str, Any]:
    """Build a list-level Work item dict from a Builder task dict."""
    return {
        "work_id": _build_work_id(task["id"]),
        "source": SOURCE_BUILDER,
        "source_id": task["id"],
        "title": task.get("title", ""),
        "summary": task.get("description"),
        "state": work_state,
        "source_state": task["state"],
        "priority": task.get("priority", 0),
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
        "blocker": task.get("blocked_reason"),
        "error": task.get("last_error"),
        "latest_run": None,
        "latest_pr": None,
        "evidence": None,
        "links": [],
    }


# ---------------------------------------------------------------------------
# Projection: get single work item
# ---------------------------------------------------------------------------


def get_work(
    work_id: str,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Return a single work item with full detail.

    Raises:
        WorkNotFoundError: if the work ID does not exist.
        WorkSourceError: if the work ID prefix is unrecognised.
        WorkStateError: if the Builder task state is unrecognised.
    """
    source, task_id = _parse_work_id(work_id)

    task = bq.get_task(task_id, db_path=db_path)
    if task is None:
        raise WorkNotFoundError(f"work {work_id!r} not found")

    work_state = _normalize_state(task["state"])

    # Latest run — fail loud if the read fails.
    latest_run: dict[str, Any] | None = None
    runs = bq.list_runs(task_id=task_id, db_path=db_path)
    if runs:
        latest_run = runs[-1]

    # Latest attempt — fail loud if the read fails.
    latest_attempt: dict[str, Any] | None = None
    bridge_ext = task.get("bridge_external_id") or ""
    if bridge_ext and "/" in bridge_ext:
        initiative_id, packet_id = bridge_ext.split("/", 1)
        attempts = ba.list_attempts(
            initiative_id, packet_id=packet_id, db_path=db_path
        )
        if attempts:
            latest_attempt = attempts[-1]

    # Latest PR link — fail loud if the read fails.
    latest_pr: dict[str, Any] | None = None
    try:
        pr_links = bq.get_pr_links(task_id, db_path=db_path)
        if pr_links:
            latest_pr = pr_links[-1]
    except TaskNotFoundError:
        pass  # No PR links for this task.

    # Errors from the task and its last run.
    errors: list[str] = []
    failure_reason = task.get("failure_reason")
    if failure_reason:
        errors.append(str(failure_reason))
    last_error = task.get("last_error")
    if last_error:
        errors.append(str(last_error))
    if latest_run and latest_run.get("final_report"):
        report = latest_run["final_report"]
        if isinstance(report, dict):
            report_errors = report.get("errors") or report.get("error")
            if report_errors:
                if isinstance(report_errors, list):
                    errors.extend(str(e) for e in report_errors)
                else:
                    errors.append(str(report_errors))

    # Evidence: run output, attempt output, and PR links — never invented.
    evidence: dict[str, Any] = {}
    if latest_run:
        if latest_run.get("log_path"):
            evidence["run_log"] = latest_run["log_path"]
        run_report = latest_run.get("final_report")
        if run_report:
            evidence["run_report"] = run_report
    if latest_attempt:
        impl = latest_attempt.get("implementation_json")
        if impl:
            evidence["implementation"] = impl
        validation = latest_attempt.get("validation_json")
        if validation:
            evidence["validation"] = validation
    if latest_pr:
        evidence["pr"] = latest_pr

    # Links: PR links and bridge URLs.
    links: list[dict[str, str]] = []
    if latest_pr:
        if latest_pr.get("pr_url"):
            links.append({"type": "pr", "url": latest_pr["pr_url"]})
    bridge_comment = task.get("bridge_comment_url")
    if bridge_comment:
        links.append({"type": "bridge", "url": bridge_comment})

    return {
        "work_id": work_id,
        "source": SOURCE_BUILDER,
        "source_id": task["id"],
        "title": task.get("title", ""),
        "summary": task.get("description"),
        "state": work_state,
        "source_state": task["state"],
        "priority": task.get("priority", 0),
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
        "blocker": task.get("blocked_reason"),
        "error": last_error,
        "latest_run": latest_run,
        "latest_pr": latest_pr,
        "evidence": evidence or None,
        "links": links,
    }


# ---------------------------------------------------------------------------
# Projection: get work events
# ---------------------------------------------------------------------------


def get_work_events(
    work_id: str,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Return all events for a work item in chronological order.

    Events are returned in exactly the Builder append-only order with
    source timestamps and source event identity preserved.

    Raises:
        WorkNotFoundError: if the work ID does not exist.
        WorkSourceError: if the work ID prefix is unrecognised.
    """
    _source, task_id = _parse_work_id(work_id)

    try:
        events = bq.list_events(task_id, db_path=db_path)
    except TaskNotFoundError as exc:
        raise WorkNotFoundError(f"work {work_id!r} not found") from exc

    return events
