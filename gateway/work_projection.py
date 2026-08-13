"""Project Builder snapshot facts into the product Work read model."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from gateway._work_projection_item import _project_work_item
from gateway._work_projection_support import (
    _count_states,
    _project_queue,
    _source_projection,
    _timestamp,
)

SCHEMA_VERSION = 1
WORK_TTL_SECONDS = 30
WORK_ITEM_LIMIT = 50


def project_work_snapshot(builder_status, *, now=None):
    """Return the schema-v1 product Work snapshot from Builder snapshot facts."""
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    observed_at = _timestamp(observed)
    valid_until = _timestamp(observed + timedelta(seconds=WORK_TTL_SECONDS))
    items = [_project_work_item(initiative) for initiative in builder_status.get("initiatives", [])]
    bounded_items = items[:WORK_ITEM_LIMIT]
    return {
        "schema_version": SCHEMA_VERSION,
        "observed_at": observed_at,
        "valid_until": valid_until,
        "source": _source_projection(builder_status),
        "counts": _count_states(bounded_items),
        "queue": _project_queue(builder_status.get("queue")),
        "items": bounded_items,
        "item_limit": WORK_ITEM_LIMIT,
        "total_items": len(items),
    }
