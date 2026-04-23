import json
import os
from datetime import datetime

from pydantic import BaseModel

try:
    from src.core.event_store import append_event as _append_event
    _EVENT_STORE_AVAILABLE = True
except ImportError:
    _EVENT_STORE_AVAILABLE = False

DEFAULT_CANONICAL_LOG = "canonical_log.jsonl"
DEFAULT_QUARANTINE_LOG = "quarantine_log.jsonl"

def log_canonical(model: BaseModel, log_path: str = DEFAULT_CANONICAL_LOG):
    """Log any validated Pydantic model to the canonical log."""
    schema = model.__class__.__name__
    data = model.model_dump()
    data["_schema"] = schema

    correlation_id = os.environ.get("CORRELATION_ID")
    if correlation_id:
        data["_correlation_id"] = correlation_id

    # Get a globally ordered sequence number from the event store
    if _EVENT_STORE_AVAILABLE:
        try:
            seq_id = _append_event(schema, data, correlation_id)
            data["_seq_id"] = seq_id
        except Exception:
            pass

    with open(log_path, "a") as f:
        f.write(json.dumps(data) + "\n")

def log_entity(entity: BaseModel, log_path: str = DEFAULT_CANONICAL_LOG):
    """Backwards compatibility for log_entity."""
    log_canonical(entity, log_path)

def log_quarantine(raw_data: dict, error: str, log_path: str = DEFAULT_QUARANTINE_LOG):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "raw_data": raw_data,
        "error": error
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
