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

On top of that baseline, ``gateway.action_grants`` records what the *user* has
standing-decided (allow/ask/deny for a scope, optionally expiring, session-bound
or spend-capped) and ``execute`` consults it before dispatch. A grant can
authorize an action the tier sheet would have asked about; it can never make a
disabled kind or a missing executor valid, because those are refused first.

Public API:
  propose(*, source_kind, kind, title, preview, source_id=None, payload=None,
          scope_type="global", scope_id="", session_id=None,
          estimated_cost_usd=None) -> dict
  approve(action_id) -> dict
  reject(action_id) -> dict
  execute(action_id) -> dict
  get(action_id) -> dict | None
  list_actions(status=None, limit=50) -> list[dict]
  reconcile_stale_executing() -> int   # startup: orphaned `executing` -> `unknown`
  reload_registry() -> None   # test seam; rebuilds from ACTION_TIERS_FILE
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from typing import Any, Callable

from gateway import action_grants, calendar_integration, delegation, storage_router, undo_journal
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
    "packet.delegate": "title",
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
    """The action must be approved before it can execute (403-shaped).

    Raised when the policy layer's answer is "ask" — either the signed tier
    requires per-action approval, or a scoped grant says to ask every time.
    """


class GrantDenied(ActionError):
    """A scoped user grant denies this action outright (403-shaped).

    Distinct from :class:`TierViolation`: approving the individual proposal
    does not clear it. The grant has to be revoked first.
    """


class ActionNotFound(ActionError):
    """No action row with that id (404-shaped)."""


class ApprovalIdentityMismatch(ActionError):
    """An approved action changed after the user approved it."""


class ActionStateError(ActionError):
    """The action is in the wrong status for the requested transition (409-shaped)."""


def init_db() -> None:
    """Apply pending migrations. Idempotent."""
    kitty_db.migrate(db_file=ACTIONS_DB_FILE)


# --- Executors -------------------------------------------------------------
# Each takes the action payload and returns a human-readable result string, or
# raises to signal a failed execution (recorded, never retried).


def _exec_todo_create(payload: dict[str, Any]) -> tuple[str, str | None]:
    """Create a todo and record an undo journal entry.

    Returns (result_string, undo_journal_id). If journal recording fails after
    todo creation, compensates by deleting the todo. If compensation cannot be
    proven, returns a result indicating unknown outcome and no journal_id.
    """
    content = str(payload["content"]).strip()
    todo = storage_router.add_todo(content)
    todo_id = int(todo["id"])
    result_text = f"todo created (id={todo_id}): {todo.get('content', content)}"

    # Record undo journal entry for the created todo
    try:
        journal_id = undo_journal.record(
            entity_type="todo",
            entity_id=str(todo_id),
            operation="create",
            before=None,  # no before state for create
            after={"id": todo_id, "content": content, "status": "pending"},
        )
        return result_text, journal_id
    except Exception as exc:
        # Journal recording failed — try to compensate by deleting the todo
        logger.warning(
            "action: undo journal record failed for todo %s, attempting compensation: %s",
            todo_id,
            exc,
        )
        try:
            deleted = storage_router.delete_todo(todo_id)
        except Exception as comp_exc:
            # Compensation raised an exception (e.g., DB error)
            logger.error(
                "action: compensation failed for todo %s after journal failure: %s",
                todo_id,
                comp_exc,
            )
            return (
                f"UNKNOWN_OUTCOME: todo {todo_id} created but undo journal failed "
                f"and compensation unproven — manual review required",
                None,
            )
        if deleted:
            # Compensation confirmed — the todo is gone, no journal entry exists
            raise RuntimeError(
                f"todo created but undo journal record failed; "
                f"compensated by deleting todo {todo_id}"
            ) from exc
        else:
            # delete_todo returned False — todo not found (already deleted?)
            logger.error(
                "action: compensation unproven for todo %s after journal failure "
                "(delete_todo returned False)",
                todo_id,
            )
            return (
                f"UNKNOWN_OUTCOME: todo {todo_id} created but undo journal failed "
                f"and compensation unproven — manual review required",
                None,
            )


def _exec_note_draft(payload: dict[str, Any]) -> tuple[str, None]:
    content = str(payload["content"])
    title = (str(payload.get("title") or "").strip()) or "draft"
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    # uuid suffix so two same-title drafts in the same second cannot collide and
    # silently overwrite each other while both report success.
    path = DRAFTS_DIR / f"{int(time.time())}-{_slug(title)}-{uuid.uuid4().hex[:8]}.md"
    path.write_text(f"# {title}\n\n{content}\n", encoding="utf-8")
    return f"draft written to {path}", None


def _exec_packet_delegate(payload: dict[str, Any]) -> tuple[str, None]:
    # The action row itself carries id/title; the payload carries the packet
    # body fields. Build a minimal action-shaped dict for the renderer.
    action = {"payload": payload}
    path = delegation.write_packet(action)
    return f"packet written to {path}", None


def _exec_calendar_create(payload: dict[str, Any]) -> tuple[str, None]:
    title = str(payload["title"]).strip()
    ok = calendar_integration.create(
        title,
        start_time=payload.get("start_time"),
        end_time=payload.get("end_time"),
        notes=payload.get("notes", ""),
    )
    if not ok:
        raise RuntimeError("calendar create failed (osascript unavailable or Calendar rejected it)")
    return f"calendar event created: {title}", None


_EXECUTORS: dict[str, Callable[[dict[str, Any]], tuple[str, str | None]]] = {
    "todo.create": _exec_todo_create,
    "note.draft": _exec_note_draft,
    "packet.delegate": _exec_packet_delegate,
    "calendar.event.create": _exec_calendar_create,
}


_REGISTRY: dict[
    str, tuple[str, Callable[[dict[str, Any]], tuple[str, str | None]]]
] | None = None


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


def _build_registry() -> dict[str, tuple[str, Callable[[dict[str, Any]], tuple[str, str | None]]]]:
    tiers, disabled = _load_tiers()
    registry: dict[str, tuple[str, Callable[[dict[str, Any]], tuple[str, str | None]]]] = {}
    for kind, fn in _EXECUTORS.items():
        if kind in disabled:
            raise ActionConfigError(
                f"executor {kind!r} is in _disabled_v1 — it must not be registered"
            )
        if kind not in tiers:
            raise ActionConfigError(f"executor {kind!r} has no tier in {ACTION_TIERS_FILE.name}")
        registry[kind] = (tiers[kind], fn)
    return registry


def _registry() -> dict[str, tuple[str, Callable[[dict[str, Any]], tuple[str, str | None]]]]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    return _REGISTRY


def reload_registry() -> None:
    """Rebuild the registry from the current ACTION_TIERS_FILE. Test seam."""
    global _REGISTRY
    _REGISTRY = _build_registry()


def effective_risk_tier(kind: str) -> str | None:
    """Return the tier enforced *now* for a registered action kind.

    Action rows retain the tier stamped when proposed for audit history, but
    execution deliberately consults the current signed registry. UI callers
    need both values so they never offer a control the executor will refuse.
    """
    entry = _registry().get(kind)
    return entry[0] if entry is not None else None


# --- Lifecycle -------------------------------------------------------------


def propose(
    *,
    source_kind: str,
    kind: str,
    title: str,
    preview: str,
    source_id: str | None = None,
    payload: dict[str, Any] | None = None,
    scope_type: str = "global",
    scope_id: str = "",
    session_id: str | None = None,
    estimated_cost_usd: float | None = None,
) -> dict[str, Any]:
    """Record a proposed action. Rejects unknown/disabled kinds and bad payloads.

    ``scope_type``/``scope_id`` say what this action is *for* — a project, a
    site, an integration — so a scoped grant has something to match against.
    ``estimated_cost_usd`` lets a budget-limited grant check its ceiling; left
    unset, such a grant asks rather than spending an unknown amount.
    """
    payload = payload or {}
    registry = _registry()
    if kind not in registry:
        raise UnknownActionKind(f"no executor registered for kind {kind!r}")
    tier, _ = registry[kind]
    _validate_payload(kind, payload)
    try:
        action_grants.validate_scope(scope_type, scope_id)
    except action_grants.GrantValidationError as exc:
        raise ActionPayloadError(str(exc)) from exc
    if estimated_cost_usd is not None and estimated_cost_usd < 0:
        raise ActionPayloadError("estimated_cost_usd must not be negative")

    init_db()
    with kitty_db.connect(ACTIONS_DB_FILE) as conn:
        cursor = conn.execute(
            "INSERT INTO actions (source_kind, source_id, kind, title, preview, "
            "payload, risk_tier, scope_type, scope_id, session_id, estimated_cost_usd) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                source_kind,
                source_id,
                kind,
                title,
                preview,
                json.dumps(payload),
                tier,
                scope_type,
                scope_id,
                session_id,
                estimated_cost_usd,
            ),
        )
        conn.commit()
        action_id = cursor.lastrowid
    if action_id is None:
        raise ActionError("insert did not return a row id")
    return _require(action_id)


def approve(action_id: int) -> dict[str, Any]:
    """proposed → approved, bound to the exact proposed call identity."""
    action = _require(action_id)
    return _decide(
        action_id,
        "approved",
        approval_fingerprint=_approval_fingerprint(action),
    )


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
        raise ActionStateError(f"cannot execute action {action_id} in status {status!r}")

    registry = _registry()
    if kind not in registry:
        # Kind was disabled or removed from the tier file after this row was
        # proposed — refuse rather than dispatch something no longer sanctioned.
        # This is precedence rule 1 in issue #554: no grant can reach past it.
        raise UnknownActionKind(f"no executor registered for kind {kind!r}")
    # Enforce the tier the signed sheet carries *now*, not the tier stamped on
    # the row at propose time — an escalation (e.g. T0 → T2) must gate a queued
    # action, not be bypassed by its stale risk_tier.
    tier, fn = registry[kind]
    decision = action_grants.evaluate(
        capability=kind,
        tier=tier,
        status=status,
        scope_type=action["scope_type"],
        scope_id=action["scope_id"],
        session_id=action["session_id"],
        estimated_cost_usd=action["estimated_cost_usd"],
        auto_execute_tiers=_AUTO_EXECUTE_TIERS,
    )
    if decision.outcome == "deny":
        raise GrantDenied(f"action {action_id} denied: {decision.reason}")
    if decision.outcome != "allow":
        raise TierViolation(f"action {action_id} requires approval: {decision.reason}")

    _validate_payload(kind, action["payload"])
    if status == "approved":
        approved_fingerprint = action.get("approval_fingerprint")
        current_fingerprint = _approval_fingerprint(action)
        if not approved_fingerprint or approved_fingerprint != current_fingerprint:
            raise ApprovalIdentityMismatch(
                f"action {action_id} changed after approval; fresh approval required"
            )

    # Reserve the spend before dispatching, not after it succeeds. Two actions
    # can both clear `evaluate` against the same ceiling; the conditioned
    # reservation is what stops the second one from running at all.
    cost = action["estimated_cost_usd"]
    reserved = _reserve_budget(decision, cost)

    # Claim the row atomically before any side effect: a concurrent /execute
    # (double-click, client retry) that already claimed it finds no matching
    # row here and is refused, so one action dispatches exactly once.
    if not _claim_for_execution(action_id, status):
        _release_budget(action_id, decision, cost, reserved)
        raise ActionStateError(f"action {action_id} is no longer {status!r} — already claimed")

    try:
        result, undo_journal_id = fn(action["payload"])
    except Exception as exc:
        logger.warning("action %s (%s) failed: %s", action_id, kind, exc)
        # No side effect happened, so the reservation must go back rather than
        # quietly eating part of the user's ceiling.
        _release_budget(action_id, decision, cost, reserved)
        return _finish(action_id, "failed", f"{type(exc).__name__}: {exc}", None)
    # Check for unknown outcome marker from todo.create compensation failure
    if result.startswith("UNKNOWN_OUTCOME:"):
        _release_budget(action_id, decision, cost, reserved)
        return _finish(action_id, "unknown", result, None)
    return _finish(action_id, "executed", result, undo_journal_id)


def _reserve_budget(decision: action_grants.Decision, cost_usd: float | None) -> bool:
    """Hold this action's cost against the grant that authorized it.

    Returns whether a reservation was taken. Raises :class:`TierViolation` when
    the ceiling can no longer absorb the cost — the user is asked rather than
    the spend happening anyway.
    """
    if not decision.charges_budget or decision.grant_id is None or cost_usd is None:
        return False
    try:
        action_grants.record_spend(decision.grant_id, cost_usd)
    except action_grants.GrantValidationError as exc:
        raise TierViolation(f"budget exhausted before execution: {exc}") from exc
    return True


def _release_budget(
    action_id: int,
    decision: action_grants.Decision,
    cost_usd: float | None,
    reserved: bool,
) -> None:
    """Return a reservation for a side effect that never happened."""
    if not reserved or decision.grant_id is None or cost_usd is None:
        return
    try:
        action_grants.release_spend(decision.grant_id, cost_usd)
    except action_grants.GrantError as exc:
        # Over-reserved is the safe direction: the ceiling stays conservative
        # until the user inspects it. Loud, never silent.
        logger.error(
            "action %s did not run but its $%s reservation on grant %s could not "
            "be released: %s",
            action_id,
            cost_usd,
            decision.grant_id,
            exc,
        )


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
        row = conn.execute(f"SELECT {_COLUMNS} FROM actions WHERE id = ?", (action_id,)).fetchone()
    return _row_to_action(row) if row else None


def reconcile_stale_executing() -> int:
    """Mark actions orphaned mid-execution by a gateway restart as outcome-unknown.

    A row still ``executing`` at startup was claimed by a coroutine that no
    longer exists — the executor may have completed the external effect,
    partially completed it, or never run at all. There is no way to tell
    which, so it is never blindly retried (that could duplicate a completed
    effect) and never silently left ``executing`` forever (nothing could ever
    query, retry, or resolve it). It is moved to a terminal ``unknown``
    status with an explanatory result so it surfaces for manual review, the
    same as an orphaned image job or autonomy session.

    Returns the number of rows reconciled.
    """
    init_db()
    now = time.time()
    with kitty_db.connect(ACTIONS_DB_FILE) as conn:
        cursor = conn.execute(
            "UPDATE actions SET status = 'unknown', result = ?, executed_at = ?, undo_journal_id = NULL "
            "WHERE status = 'executing'",
            (
                "gateway restarted mid-execution; outcome unknown — not "
                "retried automatically, needs manual review",
                now,
            ),
        )
        conn.commit()
        return int(cursor.rowcount or 0)


def list_actions_scoped(
    *, source_ids: set[str] | None = None, project_scope_ids: set[str] | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    """Return newest actions matching chat-source or project scope, then apply limit."""
    source_values = sorted(value for value in (source_ids or set()) if value)
    project_values = sorted(value for value in (project_scope_ids or set()) if value)
    if not source_values and not project_values:
        return []
    clauses: list[str] = []
    params: list[Any] = []
    if source_values:
        marks = ",".join("?" for _ in source_values)
        clauses.append(f"(source_kind = 'chat' AND source_id IN ({marks}))")
        params.extend(source_values)
    if project_values:
        marks = ",".join("?" for _ in project_values)
        clauses.append(f"(scope_type = 'project' AND scope_id IN ({marks}))")
        params.extend(project_values)
    params.append(limit)
    init_db()
    with kitty_db.connect(ACTIONS_DB_FILE) as conn:
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM actions WHERE {' OR '.join(clauses)} ORDER BY id DESC LIMIT ?",
            tuple(params),
        ).fetchall()
    return [_row_to_action(row) for row in rows]


def list_actions(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    with kitty_db.connect(ACTIONS_DB_FILE) as conn:
        if status is None:
            rows = conn.execute(
                f"SELECT {_COLUMNS} FROM actions ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {_COLUMNS} FROM actions WHERE status = ? ORDER BY id DESC LIMIT ?",
                (status, limit),
            ).fetchall()
    return [_row_to_action(r) for r in rows]


# --- Internals -------------------------------------------------------------


def _decide(
    action_id: int,
    new_status: str,
    *,
    approval_fingerprint: str | None = None,
) -> dict[str, Any]:
    action = _require(action_id)
    if action["status"] != "proposed":
        raise ActionStateError(
            f"only proposed actions can be {new_status}; action {action_id} is {action['status']}"
        )
    init_db()
    with kitty_db.connect(ACTIONS_DB_FILE) as conn:
        # Condition on proposed + check rowcount so a racing approve/reject
        # cannot overwrite an already-recorded decision.
        cursor = conn.execute(
            "UPDATE actions SET status = ?, decided_at = ?, approval_fingerprint = ? "
            "WHERE id = ? AND status = 'proposed'",
            (new_status, time.time(), approval_fingerprint, action_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise ActionStateError(
                f"action {action_id} was already decided by a concurrent request"
            )
    return _require(action_id)


def _finish(action_id: int, status: str, result: str, undo_journal_id: str | None = None) -> dict[str, Any]:
    init_db()
    with kitty_db.connect(ACTIONS_DB_FILE) as conn:
        conn.execute(
            "UPDATE actions SET status = ?, result = ?, executed_at = ?, undo_journal_id = ? WHERE id = ?",
            (status, result, time.time(), undo_journal_id, action_id),
        )
        conn.commit()
    return _require(action_id)


def _require(action_id: int) -> dict[str, Any]:
    action = get(action_id)
    if action is None:
        raise ActionNotFound(f"no action with id {action_id}")
    return action


def _approval_fingerprint(action: dict[str, Any]) -> str:
    """Canonical identity for the exact side effect a one-shot approval covers."""
    identity = {
        "kind": action["kind"],
        "payload": action["payload"],
        "scope_type": action["scope_type"],
        "scope_id": action["scope_id"],
        "session_id": action["session_id"],
        "estimated_cost_usd": action["estimated_cost_usd"],
        "source_kind": action["source_kind"],
        "source_id": action["source_id"],
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_payload(kind: str, payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ActionPayloadError(f"{kind} payload must be an object")
    field = _PAYLOAD_REQUIRED.get(kind)
    if field is None:
        return
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ActionPayloadError(f"{kind} payload requires a non-empty {field!r}")


def _slug(text: str) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in text.strip()]
    slug = "".join(keep).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug[:60] or "draft"


_COLUMNS = (
    "id, created_at, source_kind, source_id, kind, title, preview, payload, "
    "risk_tier, status, result, decided_at, executed_at, scope_type, scope_id, "
    "session_id, estimated_cost_usd, approval_fingerprint, undo_journal_id"
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
        "scope_type": row["scope_type"],
        "scope_id": row["scope_id"],
        "session_id": row["session_id"],
        "estimated_cost_usd": row["estimated_cost_usd"],
        "approval_fingerprint": row["approval_fingerprint"],
        "undo_journal_id": row["undo_journal_id"],
    }
