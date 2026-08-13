"""Work spine — read-only projection over public Builder read APIs.

Provides a stable ``WorkItem`` view of Builder queue state using the
``builder:<task_id>`` identity scheme. No new Work database: every query
delegates to the public read surfaces of the Builder modules.

Known Builder task states map to identical Work states. An unknown task state
from the Builder store raises ``WorkStateError`` immediately — no silent
defaulting to ``unknown``.
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

# Normalized Work states mirror the Builder task state machine.
# Every Builder state in _VALID_STATES maps one-to-one here.
WORK_STATE_QUEUED = "queued"
WORK_STATE_CLAIMED = "claimed"
WORK_STATE_RUNNING = "running"
WORK_STATE_BLOCKED = "blocked"
WORK_STATE_PR_OPENED = "pr_opened"
WORK_STATE_AWAITING_REVIEW = "awaiting_review"
WORK_STATE_COMPLETED = "completed"
WORK_STATE_FAILED = "failed"
WORK_STATE_CANCELLED = "cancelled"

_VALID_WORK_STATES = frozenset({
    WORK_STATE_QUEUED,
    WORK_STATE_CLAIMED,
    WORK_STATE_RUNNING,
    WORK_STATE_BLOCKED,
    WORK_STATE_PR_OPENED,
    WORK_STATE_AWAITING_REVIEW,
    WORK_STATE_COMPLETED,
    WORK_STATE_FAILED,
    WORK_STATE_CANCELLED,
})

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
    bq.QUEUED: WORK_STATE_QUEUED,
    bq.CLAIMED: WORK_STATE_CLAIMED,
    bq.RUNNING: WORK_STATE_RUNNING,
    bq.BLOCKED: WORK_STATE_BLOCKED,
    bq.PR_OPENED: WORK_STATE_PR_OPENED,
    bq.AWAITING_REVIEW: WORK_STATE_AWAITING_REVIEW,
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

    Raises ``WorkNotFoundError`` if the prefix is not recognised.
    """
    if work_id.startswith(WORK_ID_PREFIX):
        return "builder", work_id[len(WORK_ID_PREFIX):]
    raise WorkSourceError(
        f"work ID {work_id!r} has unrecognised source prefix; "
        f"expected {WORK_ID_PREFIX!r}<task_id>"
    )


def _build_work_id(task_id: str) -> str:
    """Return a ``builder:<task_id>`` work ID for the given task."""
    return f"{WORK_ID_PREFIX}{task_id}"


def _builder_source_label(task: dict[str, Any]) -> str:
    """Return a human-readable source label for a Builder task.

    Uses ``bridge_source`` when available, otherwise ``"builder_queue"``.
    """
    bridge = task.get("bridge_source")
    if bridge and isinstance(bridge, str) and bridge.strip():
        return bridge
    return "builder_queue"


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

    Args:
        state: Filter by normalized Work state.
        source: Filter by Builder ``bridge_source`` (e.g. ``"initiative"``).
        limit: Maximum items to return (clamped to 1-500).

    Returns:
        A list of work item dicts, each with:
        ``work_id``, ``state``, ``source``, ``title``, ``task_id``,
        ``created_at``, ``updated_at``, ``blocked_reason`` (or None).

    Raises:
        WorkStateError: if *state* is not a recognised Work state.
    """
    if state is not None and state not in _VALID_WORK_STATES:
        raise WorkStateError(
            f"unrecognised Work state {state!r}; "
            f"valid: {sorted(_VALID_WORK_STATES)}"
        )

    # Map Work state back to Builder state for the query.
    builder_state: str | None = None
    if state is not None:
        # Reverse lookup: find the builder state for this work state.
        for bs, ws in _BUILDER_TO_WORK_STATE.items():
            if ws == state:
                builder_state = bs
                break
        if builder_state is None:
            raise WorkStateError(
                f"cannot resolve Work state {state!r} to a Builder state"
            )

    tasks = bq.list_tasks(state=builder_state, db_path=db_path)

    # Filter by source (bridge_source) and clamp limit.
    # NOTE: bq.list_tasks has no source filter, so we post-filter in Python.
    if source is not None:
        tasks = [
            t for t in tasks
            if (t.get("bridge_source") or "builder_queue") == source
        ]

    if limit < 1:
        limit = 1
    elif limit > 500:
        limit = 500
    tasks = tasks[:limit]

    result: list[dict[str, Any]] = []
    for task in tasks:
        try:
            work_state = _normalize_state(task["state"])
        except WorkStateError:
            # Fail loud: unknown Builder state should not pass silently.
            raise
        result.append({
            "work_id": _build_work_id(task["id"]),
            "state": work_state,
            "source": _builder_source_label(task),
            "title": task.get("title", ""),
            "task_id": task["id"],
            "created_at": task.get("created_at"),
            "updated_at": task.get("updated_at"),
            "blocked_reason": task.get("blocked_reason"),
        })

    return result


# ---------------------------------------------------------------------------
# Projection: get single work item
# ---------------------------------------------------------------------------


def get_work(
    work_id: str,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Return a single work item with full detail.

    The detail includes the latest run, latest attempt, latest PR link,
    errors, and timestamps.

    Raises:
        WorkNotFoundError: if the work ID does not exist.
        WorkSourceError: if the work ID prefix is unrecognised.
        WorkStateError: if the Builder task state is unrecognised.
    """
    source, task_id = _parse_work_id(work_id)

    task = bq.get_task(task_id, db_path=db_path)
    if task is None:
        raise WorkNotFoundError(f"work {work_id!r} not found")

    try:
        work_state = _normalize_state(task["state"])
    except WorkStateError:
        raise

    # Latest run for this task.
    latest_run: dict[str, Any] | None = None
    try:
        runs = bq.list_runs(task_id=task_id, db_path=db_path)
        if runs:
            latest_run = runs[-1]
    except Exception as exc:
        logger.warning("Failed to list runs for task %s: %s", task_id, exc)

    # Latest attempt for this task (across all packets in all initiatives).
    latest_attempt: dict[str, Any] | None = None
    try:
        # Attempts are keyed to initiative_id+packet_id, not task_id directly.
        # The task's bridge_external_id is "<initiative_id>/<packet_id>".
        bridge_ext = task.get("bridge_external_id") or ""
        if bridge_ext and "/" in bridge_ext:
            initiative_id, packet_id = bridge_ext.split("/", 1)
            attempts = ba.list_attempts(
                initiative_id, packet_id=packet_id, db_path=db_path
            )
            if attempts:
                latest_attempt = attempts[-1]
    except Exception as exc:
        logger.warning("Failed to list attempts for task %s: %s", task_id, exc)

    # Latest PR link.
    latest_pr: dict[str, Any] | None = None
    try:
        pr_links = bq.get_pr_links(task_id, db_path=db_path)
        if pr_links:
            latest_pr = pr_links[-1]
    except TaskNotFoundError:
        pass  # No PR links for this task.
    except Exception as exc:
        logger.warning("Failed to get PR links for task %s: %s", task_id, exc)

    # Errors from the task and its last run.
    errors: list[str] = []
    failure_reason = task.get("failure_reason")
    if failure_reason:
        errors.append(str(failure_reason))
    if latest_run and latest_run.get("final_report"):
        report = latest_run["final_report"]
        if isinstance(report, dict):
            report_errors = report.get("errors") or report.get("error")
            if report_errors:
                if isinstance(report_errors, list):
                    errors.extend(str(e) for e in report_errors)
                else:
                    errors.append(str(report_errors))

    return {
        "work_id": work_id,
        "state": work_state,
        "source": _builder_source_label(task),
        "title": task.get("title", ""),
        "description": task.get("description"),
        "task_id": task["id"],
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
        "blocked_reason": task.get("blocked_reason"),
        "failure_reason": failure_reason,
        "errors": errors,
        "latest_run": latest_run,
        "latest_attempt": latest_attempt,
        "latest_pr": latest_pr,
    }


# ---------------------------------------------------------------------------
# Projection: get work events
# ---------------------------------------------------------------------------


def get_work_events(
    work_id: str,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Return all events for a work item in chronological order.

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
