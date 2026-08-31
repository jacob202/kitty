"""Single schema entry point for the Builder domain.

Builder's durable SQLite store spans several modules: the queue core
(``gateway._queue_db``), branch leases (``gateway._branch_leases``), initiative
and packet tables (``gateway.builder_initiative``), and attempt tables
(``gateway.builder_attempt``). Each module keeps its DDL and migrations beside
the code that owns the rows, but callers that need a ready-to-use durable store
must not chase that chain themselves.

:func:`ensure_builder_schema` is the one idempotent, explicitly callable entry
point. It applies every module's schema in dependency order and is safe to call
repeatedly. Read-only projections (``builder_status``, MCP context, the
control-plane summary) never call it: inspection must fail loudly rather than
create or migrate storage.
"""

from __future__ import annotations

from pathlib import Path

from gateway import builder_attempt as _attempt
from gateway import builder_initiative as _initiative
from gateway import builder_queue as _queue


def ensure_builder_schema(db_path: Path | None = None) -> None:
    """Create/migrate the full Builder schema.

    Idempotent: every layer's migration is a no-op when the schema is already
    current. Writers may also call their own module ``init_db`` directly, but
    bootstrap code and anything that must produce a fully usable store should
    call this once.
    """
    _queue.init_db(db_path)
    _initiative.init_db(db_path)
    _attempt.init_db(db_path)
