"""Action queue with enforced risk tiers (P3, docs/packets/003).

This is the only path from "Kitty thinks X should happen" to "X happened,
recorded." Every action is a row: proposed → (approved|rejected) →
executed|failed. No code elsewhere may cause an external or state-mutating
effect without going through ``execute`` here.

Tiers are loaded read-only at startup from ``config/action_tiers.json`` (signed
off by Jacob) and enforced in the executor registry, in code:

- **T0** — may execute automatically from ``proposed``; every execution is
  recorded.
- **T1** — may create *local* draft artifacts automatically from ``proposed``;
  transmits nothing and performs no external side effect.
- **T2** — requires explicit per-action approval before execution.

A kind absent from the tier file cannot be registered. A kind listed under
``_disabled_v1`` must not exist as an executor at all — proposing one is a hard
error. There is no runtime mutation API for tiers and no retry/scheduling of
failed actions (both out of scope for v1).

Public API:
  propose(*, source_kind, kind, title, preview, source_id=None, payload=None) -> dict
  approve(action_id) -> dict
  reject(action_id) -> dict
  execute(action_id) -> dict
  get(action_id) -> dict | None
  list_actions(status=None, limit=50) -> list[dict]
  reload_registry() -> None   # test seam; rebuilds from ACTION_TIERS_FILE
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Callable

from gateway import calendar_integration, storage_router
from gateway import db as kitty_db
from gateway.paths import ACTION_TIERS_FILE, DRAFTS_DIR, KITTY_DB_FILE

logger = logging.getLogger("kitty.action_queue")

ACTIONS_DB_FILE = KITTY_DB_FILE

# Tiers whose actions may execute straight from `proposed`. T2 is deliberately
# excluded: it must be approved first.
_AUTO_EXECUTE_TIERS = frozenset({"T0", "T1"})

# The single field each kind's payload must carry. Checked before dispatch so a
# malformed payload can never reach an executor.
_PAYLOAD_REQUIRED: dict[str, str] = {
    "todo.create": "content",
    "note.draft": "content",
    "calendar.event.create": "title",
}


class ActionError(RuntimeError):
    """Base for action-queue errors."""


class ActionConfigError(ActionError):
    """The tier file and the executor set disagree (startup/config fault)."""


class UnknownActionKind(ActionError):
    """No executor is registered for the requested kind (400-shaped)."""


class ActionPayloadError(ActionError):
    """The payload is missing a field its kind requires (400-shaped)."""


class TierViolation(ActionError):
    """A T2 action was asked to execute without approval (403-shaped)."""


class ActionNotFound(ActionError):
    """No action row with that id (404-shaped)."""


class ActionStateError(ActionError):
    """The action is in the wrong status for the requested transition (409-shaped)."""


def init_db() -> None:
    """Apply pending migrations. Idempotent."""
    kitty_db.migrate(db_file=ACTIONS_DB_FILE)


# --- Executors -------------------------------------------------------------
# Each takes the action payload and returns a human-readable result string, or
# raises to signal a failed execution (recorded, never retried).


def _exec_todo_create(payload: dict[str, Any]) -> str:
    content = str(payload["content"]).strip()
    todo = storage_router.add_todo(content)
    return f"todo created (id={todo.get('id')}): {todo.get('content', content)}"


def _exec_note_draft(payload: dict[str, Any]) -> str:
    content = str(payload["content"])
    title = (str(payload.get("title") or "").strip()) or "draft"
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    # uuid suffix so two same-title drafts in the same second cannot collide and
    # silently overwrite each other while both report success.
    path = DRAFTS_DIR / f"{int(time.time())}-{_slug(title)}-{uuid.uuid4().hex[:8]}.md"
    path.write_text(f"# {title}\n\n{content}\n", encoding="utf-8")
    # T1 contract: produce the local artifact, transmit nothing.
    return f"draft written to {path}"


def _exec_calendar_create(payload: dict[str, Any]) -> str:
    title = str(payload["title"]).strip()
    ok = calendar_integration.create(
        title,
        start_time=payload.get("start_time"),
        end_time=payload.get("end_time"),
        notes=payload.get("notes", ""),
    )
    if not ok:
        raise RuntimeError(
            "calendar create failed (osascript unavailable or Calendar rejected it)"
        )
    return f"calendar event created: {title}"


_EXECUTORS: dict[str, Callable[[dict[str, Any]], str]] = {
    "todo.create": _exec_todo_create,
    "note.draft": _exec_note_draft,
    "calendar.event.create": _exec_calendar_create,
}


# --- Registry (tier file × executors) --------------------------------------

_REGISTRY: dict[str, tuple[str, Callable[[dict[str, Any]], str]]] | None = None


def _load_tiers() -> tuple[dict[str, str], set[str]]:
    """Read the signed tier file: {kind: tier} plus the disabled-kind set."""
    try:
        raw = json.loads(ACTION_TIERS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ActionConfigError(f"cannot read {ACTION_TIERS_FILE}: {exc}") from exc
    disabled = set(raw.get("_disabled_v1", []))
    tiers = {
        kind: tier
        for kind, tier in raw.items()
        if not kind.startswith("_") and isinstance(tier, str)
    }
    return tiers, disabled


def _build_registry() -> dict[str, tuple[str, Callable[[dict[str, Any]], str]]]:
    tiers, disabled = _load_tiers()
    registry: dict[str, tuple[str, Callable[[dict[str, Any]], str]]] = {}
    for kind, fn in _EXECUTORS.items():
        if kind in disabled:
            raise ActionConfigError(
                f"executor {kind!r} is in _disabled_v1 — it must not be registered"
            )
        if kind not in tiers:
            raise ActionConfigError(
                f"executor {kind!r} has no tier in {ACTION_TIERS_FILE.name}"
            )
        registry[kind] = (tiers[kind], fn)
    return registry


def _registry() -> dict[str, tuple[str, Callable[[dict[str, Any]], str]]]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    return _REGISTRY


def reload_registry() -> None:
    """Rebuild the registry from the current ACTION_TIERS_FILE. Test seam."""
    global _REGISTRY
    _REGISTRY = _build_registry()


# --- Lifecycle -------------------------------------------------------------


def propose(
    *,
    source_kind: str,
    kind: str,
    title: str,
    preview: str,
    source_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record a proposed action. Rejects unknown/disabled kinds and bad payloads."""
    payload = payload or {}
    registry = _registry()
    if kind not in registry:
        raise UnknownActionKind(f"no executor registered for kind {kind!r}")
    tier, _ = registry[kind]
    _validate_payload(kind, payload)

    init_db()
    with kitty_db.connect(ACTIONS_DB_FILE) as conn:
        cursor = conn.execute(
            "INSERT INTO actions (source_kind, source_id, kind, title, preview, "
            "payload, risk_tier) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (source_kind, source_id, kind, title, preview, json.dumps(payload), tier),
        )
        conn.commit()
        action_id = cursor.lastrowid
    if action_id is None:
        raise ActionError("insert did not return a row id")
    return _require(action_id)


def approve(action_id: int) -> dict[str, Any]:
    """proposed → approved."""
    return _decide(action_id, "approved")


def reject(action_id: int) -> dict[str, Any]:
    """proposed → rejected. Rejected actions stay queryable."""
    return _decide(action_id, "rejected")


def execute(action_id: int) -> dict[str, Any]:
    """Dispatch through the executor registry with tier enforcement.

    T2 requires status ``approved``; T0/T1 may run from ``proposed``. The
    executor's success text or exception is recorded on the row.
    """
    action = _require(action_id)
    status = action["status"]
    kind = action["kind"]

    if status not in ("proposed", "approved"):
        raise ActionStateError(
            f"cannot execute action {action_id} in status {status!r}"
        )

    registry = _registry()
    if kind not in registry:
        # Kind was disabled or removed from the tier file after this row was
        # proposed — refuse rather than dispatch something no longer sanctioned.
        raise UnknownActionKind(f"no executor registered for kind {kind!r}")
    # Enforce the tier the signed sheet carries *now*, not the tier stamped on
    # the row at propose time — an escalation (e.g. T0 → T2) must gate a queued
    # action, not be bypassed by its stale risk_tier.
    tier, fn = registry[kind]
    if tier not in _AUTO_EXECUTE_TIERS and status != "approved":
        raise TierViolation(
            f"{tier} action {action_id} requires approval before execution"
        )

    _validate_payload(kind, action["payload"])

    # Claim the row atomically before any side effect: a concurrent /execute
    # (double-click, client retry) that already claimed it finds no matching
    # row here and is refused, so one action dispatches exactly once.
    if not _claim_for_execution(action_id, status):
        raise ActionStateError(
            f"action {action_id} is no longer {status!r} — already claimed"
        )

    try:
        result = fn(action["payload"])
    except Exception as exc:
        logger.warning("action %s (%s) failed: %s", action_id, kind, exc)
        return _finish(action_id, "failed", f"{type(exc).__name__}: {exc}")
    return _finish(action_id, "executed", result)


def _claim_for_execution(action_id: int, expected_status: str) -> bool:
    """Atomically move proposed/approved → executing. False if already claimed."""
    init_db()
    with kitty_db.connect(ACTIONS_DB_FILE) as conn:
        cursor = conn.execute(
            "UPDATE actions SET status = 'executing' WHERE id = ? AND status = ?",
            (action_id, expected_status),
        )
        conn.commit()
        return cursor.rowcount > 0


def get(action_id: int) -> dict[str, Any] | None:
    init_db()
    with kitty_db.connect(ACTIONS_DB_FILE) as conn:
        row = conn.execute(
            f"SELECT {_COLUMNS} FROM actions WHERE id = ?", (action_id,)
        ).fetchone()
    return _row_to_action(row) if row else None


def list_actions(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    with kitty_db.connect(ACTIONS_DB_FILE) as conn:
        if status is None:
            rows = conn.execute(
                f"SELECT {_COLUMNS} FROM actions ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {_COLUMNS} FROM actions WHERE status = ? "
                "ORDER BY id DESC LIMIT ?",
                (status, limit),
            ).fetchall()
    return [_row_to_action(r) for r in rows]


# --- Internals -------------------------------------------------------------


def _decide(action_id: int, new_status: str) -> dict[str, Any]:
    action = _require(action_id)
    if action["status"] != "proposed":
        raise ActionStateError(
            f"only proposed actions can be {new_status}; "
            f"action {action_id} is {action['status']}"
        )
    init_db()
    with kitty_db.connect(ACTIONS_DB_FILE) as conn:
        # Condition on proposed + check rowcount so a racing approve/reject
        # cannot overwrite an already-recorded decision.
        cursor = conn.execute(
            "UPDATE actions SET status = ?, decided_at = ? "
            "WHERE id = ? AND status = 'proposed'",
            (new_status, time.time(), action_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise ActionStateError(
                f"action {action_id} was already decided by a concurrent request"
            )
    return _require(action_id)


def _finish(action_id: int, status: str, result: str) -> dict[str, Any]:
    init_db()
    with kitty_db.connect(ACTIONS_DB_FILE) as conn:
        conn.execute(
            "UPDATE actions SET status = ?, result = ?, executed_at = ? WHERE id = ?",
            (status, result, time.time(), action_id),
        )
        conn.commit()
    return _require(action_id)


def _require(action_id: int) -> dict[str, Any]:
    action = get(action_id)
    if action is None:
        raise ActionNotFound(f"no action with id {action_id}")
    return action


def _validate_payload(kind: str, payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ActionPayloadError(f"{kind} payload must be an object")
    field = _PAYLOAD_REQUIRED.get(kind)
    if field is None:
        return
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ActionPayloadError(
            f"{kind} payload requires a non-empty {field!r}"
        )


def _slug(text: str) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in text.strip()]
    slug = "".join(keep).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug[:60] or "draft"


_COLUMNS = (
    "id, created_at, source_kind, source_id, kind, title, preview, payload, "
    "risk_tier, status, result, decided_at, executed_at"
)


def _row_to_action(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "source_kind": row["source_kind"],
        "source_id": row["source_id"],
        "kind": row["kind"],
        "title": row["title"],
        "preview": row["preview"],
        "payload": json.loads(row["payload"]),
        "risk_tier": row["risk_tier"],
        "status": row["status"],
        "result": row["result"],
        "decided_at": row["decided_at"],
        "executed_at": row["executed_at"],
    }
