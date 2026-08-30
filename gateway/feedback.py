"""User feedback and error logging — owned substrate for the feedback endpoint.

Why this module exists (Phase 3 of the gateway deepening program):
the route handler used to swallow every I/O error with a bare
``except Exception: pass``, hiding real disk-write failures from the
operator. The new module validates inputs, writes through ``paths.py``,
and raises on failure so the route layer cannot mask a broken log.

The wire shape of every endpoint that used to live in
``routes/feedback.py`` is unchanged. The route is now a thin
request-parsing / response-shaping wrapper around these functions.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.feedback")

FEEDBACK_LOG = DATA_DIR / "feedback.jsonl"
ERROR_LOG = DATA_DIR / "kitty_errors.jsonl"


def _validate_record(record: Any, *, kind: str) -> dict:
    if not isinstance(record, dict):
        raise TypeError(f"{kind} payload must be a dict, got {type(record).__name__}")
    return record


def log_feedback(feedback: dict) -> None:
    """Append one feedback record to ``FEEDBACK_LOG``.

    Raises on any I/O failure. The caller (the route layer) does not
    catch this — a write failure is a real, loud failure that the
    operator should see in the gateway log.
    """
    record = _validate_record(feedback, kind="feedback")
    FEEDBACK_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = dict(record)
    record["timestamp"] = time.time()
    with FEEDBACK_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_error(error: dict) -> None:
    """Append one client-side error record to ``ERROR_LOG``.

    Raises on any I/O failure.
    """
    record = _validate_record(error, kind="error")
    ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = dict(record)
    record["timestamp"] = time.time()
    with ERROR_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read_jsonl(path) -> list[dict]:
    """Parse one JSONL file into a list of dicts.

    Skips malformed lines (the old code did the same) but raises on
    any file-level error so a corrupted log does not silently report
    a zero count.
    """
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError:
                continue
    return rows


def get_feedback_stats() -> dict:
    """Aggregate counts and recent samples from both feedback and error logs.

    Empty when no data has been written. Never returns mock data.
    """
    feedbacks = _read_jsonl(FEEDBACK_LOG)
    errors = _read_jsonl(ERROR_LOG)

    feedback_types: dict[str, int] = {}
    for entry in feedbacks:
        if not isinstance(entry, dict):
            continue
        ftype = str(entry.get("type", "unknown"))
        feedback_types[ftype] = feedback_types.get(ftype, 0) + 1

    error_types: dict[str, int] = {}
    for entry in errors:
        if not isinstance(entry, dict):
            continue
        etype = str(entry.get("error_type", "unknown"))
        error_types[etype] = error_types.get(etype, 0) + 1

    return {
        "total_feedback": len(feedbacks),
        "total_errors": len(errors),
        "feedback_by_type": feedback_types,
        "errors_by_type": error_types,
        "recent_feedback": feedbacks[-10:],
        "recent_errors": errors[-10:],
    }
