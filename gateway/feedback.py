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

import hashlib
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


def _require_preference_text(payload: dict, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value.strip()


def record_preference_pairs(payload: dict) -> list[str]:
    """Record explicit human A/B choices as evaluation-only feedback evidence.

    One chosen option may be paired against multiple rejected options. The
    records deliberately carry no training/routing authority; downstream
    evaluators may consume them as human evidence only.
    """
    record = _validate_record(payload, kind="preference")
    allowed = {"experiment_id", "chosen_id", "rejected_ids", "context"}
    unknown = sorted(set(record) - allowed)
    if unknown:
        raise ValueError(f"unknown preference keys: {unknown}")

    experiment_id = _require_preference_text(record, "experiment_id")
    chosen_id = _require_preference_text(record, "chosen_id")
    rejected = record.get("rejected_ids")
    if not isinstance(rejected, list) or not rejected:
        raise ValueError("rejected_ids must be a non-empty list")
    rejected_ids: list[str] = []
    for value in rejected:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("rejected_ids must contain non-empty strings")
        rejected_ids.append(value.strip())
    if len(set(rejected_ids)) != len(rejected_ids):
        raise ValueError("rejected_ids must be unique")
    if chosen_id in rejected_ids:
        raise ValueError("chosen_id cannot also be rejected")

    context_raw = record.get("context", {})
    if not isinstance(context_raw, dict):
        raise ValueError("context must be an object")
    context: dict[str, str] = {}
    for key, value in context_raw.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("context keys must be non-empty strings")
        if not isinstance(value, str) or not value.strip():
            raise ValueError("context values must be non-empty strings")
        context[key.strip()] = value.strip()

    existing_pair_ids = {
        str(row.get("pair_id"))
        for row in _read_jsonl(FEEDBACK_LOG)
        if isinstance(row, dict) and row.get("type") == "preference_pair" and row.get("pair_id")
    }
    pair_ids: list[str] = []
    for rejected_id in rejected_ids:
        identity = json.dumps(
            {
                "experiment_id": experiment_id,
                "chosen_id": chosen_id,
                "rejected_id": rejected_id,
                "context": context,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        pair_id = "pref_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        if pair_id not in existing_pair_ids:
            log_feedback(
                {
                    "type": "preference_pair",
                    "schema_version": 1,
                    "pair_id": pair_id,
                    "experiment_id": experiment_id,
                    "chosen_id": chosen_id,
                    "rejected_id": rejected_id,
                    "context": context,
                    "source": "human_explicit",
                    "use": "evaluation_only",
                }
            )
            existing_pair_ids.add(pair_id)
        pair_ids.append(pair_id)
    return pair_ids


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
