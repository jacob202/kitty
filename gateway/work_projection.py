from datetime import datetime, timedelta, timezone

from gateway._work_projection_item import _project_work_item
from gateway._work_projection_support import (
    _count_states,
    _project_queue,
    _rank_work_items,
    _select_bounded_work_items,
    _source_projection,
    _timestamp,
)

SCHEMA_VERSION = 1
WORK_TTL_SECONDS = 30
WORK_ITEM_LIMIT = 50


def _build(source, now=None):
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    initiatives = source.get("initiatives", [])
    historical = [item for item in initiatives if item.get("superseded_by")]
    current = [item for item in initiatives if not item.get("superseded_by")]
    items = [_project_work_item(item) for item in current]
    ranked = _rank_work_items(items)
    bounded = _select_bounded_work_items(ranked, WORK_ITEM_LIMIT)
    return {
        "schema_version": SCHEMA_VERSION,
        "observed_at": _timestamp(observed),
        "valid_until": _timestamp(observed + timedelta(seconds=WORK_TTL_SECONDS)),
        "source": _source_projection(source),
        "counts": _count_states(items),
        "queue": _project_queue(source.get("queue")),
        "items": bounded,
        "item_limit": WORK_ITEM_LIMIT,
        "total_items": len(items),
        "historical_items": len(historical),
    }


project_work_snapshot = _build
