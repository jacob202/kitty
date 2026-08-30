"""Unified activity timeline — a read-only projection over existing evidence.

Kitty's activity lives in several existing ledgers (Automation Run evidence,
image jobs, explicit memory, signals, and approval/grants). This module merges
them into one chronological view without introducing a new event store.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from gateway import action_grants, automation_runs, explicit_memory, image_jobs, signal_store

VALID_FILTERS = frozenset({"all", "automations", "images", "memory", "system", "failures"})

AUTOMATION_FAILURE_STATUSES = frozenset(
    {"failed", "interrupted", "action_unavailable", "source_unavailable", "policy_refused"}
)

IMAGE_FAILURE_STATUSES = frozenset({"failed"})

_MAX_SUMMARY_CHARS = 120


def _truncate(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    return value[:limit]


def _to_ts(value: Any) -> float:
    """Coerce a required evidence timestamp, failing loud when it is malformed."""
    if isinstance(value, bool):
        raise ValueError(f"invalid timeline timestamp {value!r}")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError as exc:
            raise ValueError(f"invalid timeline timestamp {value!r}") from exc
    raise ValueError(f"invalid timeline timestamp {value!r}")


def _automation_entries(limit: int, *, failures_only: bool = False) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for run in automation_runs.list_runs(
        limit=limit, statuses=AUTOMATION_FAILURE_STATUSES if failures_only else None
    ):
        status = run.get("status")
        ts = run.get("completed_at") or run.get("started_at")
        entries.append(
            {
                "timestamp": _to_ts(ts),
                "source": "automation",
                "category": "automations",
                "summary": run.get("action") or run.get("automation_id") or "Automation",
                "object": run.get("automation_id"),
                "status": status,
                "failed": status in AUTOMATION_FAILURE_STATUSES,
                "detail": run.get("error"),
                "evidence": run.get("id"),
            }
        )
    return entries


def _image_entries(limit: int, *, failures_only: bool = False) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    statuses = (
        frozenset({image_jobs.ImageJobStatus.FAILED}) if failures_only else None
    )
    for job in image_jobs.list_recent(limit=limit, statuses=statuses):
        status = getattr(job.status, "value", job.status)
        ts = job.finished_at or job.created_at
        entries.append(
            {
                "timestamp": _to_ts(ts),
                "source": "image",
                "category": "images",
                "summary": f"Image {job.operation or 'generation'}",
                "object": job.job_id,
                "status": status,
                "failed": status in IMAGE_FAILURE_STATUSES,
                "detail": job.normalized_error,
                "evidence": job.job_id,
            }
        )
    return entries


def _memory_entries(limit: int) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for mem in explicit_memory.list_memories(limit=limit):
        if mem.get("sensitivity") == "sensitive":
            continue
        ts = mem.get("updated_at") or mem.get("created_at")
        entries.append(
            {
                "timestamp": _to_ts(ts),
                "source": "memory",
                "category": "memory",
                "summary": _truncate(mem.get("text"), _MAX_SUMMARY_CHARS) or "Memory",
                "object": mem.get("id"),
                "status": mem.get("status"),
                "failed": False,
                "detail": mem.get("source_kind"),
                "evidence": mem.get("id"),
            }
        )
    return entries


def _signal_entries(limit: int) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for sig in signal_store.list_recent(limit=limit):
        summary = f"{sig.get('source', '')} {sig.get('kind', '')}".strip() or "Signal"
        entries.append(
            {
                "timestamp": _to_ts(sig.get("ts")),
                "source": "signal",
                "category": "system",
                "summary": summary,
                "object": sig.get("source"),
                "status": None,
                "failed": False,
                "detail": sig.get("kind"),
                "evidence": f"signal-{sig.get('id')}",
            }
        )
    return entries


def _grant_entries(limit: int) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for grant in action_grants.list_grants(include_inactive=True, limit=limit):
        status = "revoked" if grant.get("revoked_at") else grant.get("decision")
        summary = f"Grant {grant.get('decision', '')} {grant.get('capability', '')}".strip()
        entries.append(
            {
                "timestamp": _to_ts(
                    grant.get("revoked_at") if grant.get("revoked_at") else grant.get("created_at")
                ),
                "source": "grant",
                "category": "system",
                "summary": summary,
                "object": grant.get("capability"),
                "status": status,
                "failed": False,
                "detail": grant.get("reason"),
                "evidence": f"grant-{grant.get('id')}",
            }
        )
    return entries


def _matches_filter(category: str, failed: bool, filter_: str) -> bool:
    if filter_ == "all":
        return True
    if filter_ == "failures":
        return failed
    return category == filter_


def build_timeline(*, filter: str = "all", limit: int = 50) -> list[dict[str, Any]]:
    """Assemble a bounded, deduplicated, newest-first activity timeline.

    Raises ``ValueError`` for an unknown filter so callers fail loud rather than
    silently returning an empty timeline.
    """
    if filter not in VALID_FILTERS:
        raise ValueError(f"unknown timeline filter {filter!r}; expected one of {sorted(VALID_FILTERS)}")
    bounded = max(1, min(int(limit), 200))

    merged: list[dict[str, Any]] = []
    if filter == "failures":
        merged.extend(_automation_entries(bounded, failures_only=True))
        merged.extend(_image_entries(bounded, failures_only=True))
    else:
        merged.extend(_automation_entries(bounded))
        merged.extend(_image_entries(bounded))
        merged.extend(_memory_entries(bounded))
        merged.extend(_signal_entries(bounded))
        merged.extend(_grant_entries(bounded))

    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for entry in merged:
        key = (entry["source"], entry["evidence"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)

    deduped.sort(key=lambda e: e["timestamp"], reverse=True)
    return [
        e
        for e in deduped
        if _matches_filter(e["category"], e["failed"], filter)
    ][:bounded]
