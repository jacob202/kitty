"""Read-only summaries of persisted LLM token usage."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from gateway.paths import KITTY_TOKEN_LOG_FILE
from gateway.token_spend_report import filter_entries, summarize_usage

router = APIRouter(tags=["usage"])

_USAGE_FIELDS: dict[str, type] = {
    "date": str,
    "provider": str,
    "model": str,
    "operation": str,
    "usage": dict,
    "metadata": dict,
}
_USAGE_TOKEN_FIELDS = (
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "reasoning_tokens",
    "cached_tokens",
)


def _ledger_error(path: Path, line_number: int, reason: str) -> HTTPException:
    return HTTPException(
        status_code=500,
        detail=f"Usage ledger is corrupt at {path}, line {line_number}: {reason}",
    )


def _validate_usage_record(record: dict[str, Any], path: Path, line_number: int) -> None:
    for field, expected_type in _USAGE_FIELDS.items():
        if not isinstance(record.get(field), expected_type):
            raise _ledger_error(
                path,
                line_number,
                f"{field!r} must be {expected_type.__name__}",
            )

    try:
        date.fromisoformat(record["date"])
    except ValueError as exc:
        raise _ledger_error(path, line_number, "date must be ISO-8601") from exc

    usage = record["usage"]
    for field in _USAGE_TOKEN_FIELDS:
        if field not in usage:
            continue
        value = usage[field]
        if type(value) is not int or value < 0:
            raise _ledger_error(
                path,
                line_number,
                f"usage.{field} must be a non-negative integer",
            )


def _is_storage_write_record(record: dict[str, Any]) -> bool:
    return record.get("kind") == "storage_write"


def _validate_storage_write_record(record: dict[str, Any], path: Path, line_number: int) -> None:
    if not isinstance(record.get("store"), str):
        raise _ledger_error(path, line_number, "storage write 'store' must be str")
    if not isinstance(record.get("op"), str):
        raise _ledger_error(path, line_number, "storage write 'op' must be str")
    ms = record.get("ms")
    if not isinstance(ms, (int, float)) or isinstance(ms, bool):
        raise _ledger_error(path, line_number, "storage write 'ms' must be non-negative")
    if ms < 0:
        raise _ledger_error(path, line_number, "storage write 'ms' must be non-negative")
    key = record.get("key")
    if key is not None and not isinstance(key, str):
        raise _ledger_error(path, line_number, "storage write 'key' must be str or null")


def _read_usage_ledger(path: Path | None = None) -> tuple[list[dict[str, Any]], int]:
    """Load valid LLM usage rows and count valid non-LLM storage telemetry."""
    path = path or KITTY_TOKEN_LOG_FILE
    if not path.exists():
        return [], 0

    usage_records: list[dict[str, Any]] = []
    storage_write_records = 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise _ledger_error(path, line_number, "invalid JSON") from exc
                if not isinstance(record, dict):
                    raise _ledger_error(path, line_number, "record must be an object")

                if _is_storage_write_record(record):
                    _validate_storage_write_record(record, path, line_number)
                    storage_write_records += 1
                    continue

                _validate_usage_record(record, path, line_number)
                usage_records.append(record)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Usage ledger is unreadable at {path}: {exc}",
        ) from exc

    return usage_records, storage_write_records


@router.get("/usage/summary")
async def get_usage_summary(
    since: date | None = Query(default=None),
    provider: str | None = Query(default=None, min_length=1),
) -> dict[str, Any]:
    """Return persisted LLM token usage and explicitly-labelled cost estimates."""
    entries, storage_write_records = _read_usage_ledger()
    filtered_entries = filter_entries(
        entries,
        since=since.isoformat() if since else None,
        provider=provider,
    )
    summary = summarize_usage(filtered_entries)
    summary["ledger"] = {
        "llm_usage_records": len(entries),
        "storage_write_records": storage_write_records,
    }
    summary["cost_estimate_disclaimer"] = (
        "Estimated cost is calculated from Kitty's static model-price registry; "
        "it is not provider-reported billing."
    )
    return summary
