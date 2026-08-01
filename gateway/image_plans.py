"""Durable, session-owned image plans (issue #336, slice A2).

A1 made the Image Studio session durable but the plan was still an ephemeral
preview: /studio/generate re-derived everything from mutable form state, so a
field edited after the user approved the plan silently changed what rendered.
This module persists the approved ``ImagePlan`` under a stable ``plan_id`` owned
by the session that created it, and A2's dispatch path reads the render inputs
from the stored plan — never from the live form.

Boundaries:
- This module owns plan persistence only. ``image_jobs`` remains the record of
  what was rendered, and ``image_runner`` remains the only dispatch path.
  Nothing here submits work to a renderer.
- A plan is owned by exactly one session. Dispatching a plan under a different
  session is rejected at load time, so a plan id leaked between conversations
  cannot cross session boundaries.
- Every mutation and load validates and raises. There are no silent fallbacks:
  an unknown, malformed, unapproved, or cross-session plan fails loud at load
  time instead of silently dispatching form state.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from gateway import db as kitty_db
from gateway import paths as _paths
from gateway.paths import DB_MIGRATIONS_DIR

_MIGRATION_FILE = DB_MIGRATIONS_DIR / "030_image_plans.sql"

_MAX_JSON_BYTES = 65_536
_MAX_TEXT_BYTES = 10_240


class PlanStatus(str, Enum):
    """Lifecycle of a persisted image plan."""

    APPROVED = "approved"
    REJECTED = "rejected"

    def is_dispatchable(self) -> bool:
        return self is PlanStatus.APPROVED


class PlanStoreError(RuntimeError):
    """Raised when a plan store operation cannot complete safely."""


class PlanNotFoundError(PlanStoreError):
    """Raised when a plan id does not exist."""


class PlanMalformedError(PlanStoreError):
    """Raised when a persisted plan row cannot be parsed back into a plan."""


class PlanNotApprovedError(PlanStoreError):
    """Raised when dispatch targets a plan that is not approved."""


class PlanSessionMismatchError(PlanStoreError):
    """Raised when a plan is dispatched under a different session than its owner."""


@dataclass
class StoredPlan:
    """A persisted, session-owned image plan ready for dispatch."""

    plan_id: str
    session_id: str
    status: PlanStatus
    original_prompt: str
    refined_prompt: str
    character_id: str | None
    character_ref_path: str | None
    recipe_id: str | None
    guidance_tags: list[str] = field(default_factory=list)
    references: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "session_id": self.session_id,
            "status": self.status.value,
            "original_prompt": self.original_prompt,
            "refined_prompt": self.refined_prompt,
            "character_id": self.character_id,
            "character_ref_path": self.character_ref_path,
            "recipe_id": self.recipe_id,
            "guidance_tags": list(self.guidance_tags),
            "references": [dict(r) for r in self.references],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_plan_id() -> str:
    return f"imgplan_{uuid.uuid4().hex}"


def _check_json_bounded(value: str, field_name: str) -> None:
    raw = value.encode("utf-8")
    if len(raw) > _MAX_JSON_BYTES:
        raise PlanStoreError(
            f"{field_name} exceeds {_MAX_JSON_BYTES} bytes ({len(raw)} bytes supplied)"
        )
    try:
        json.loads(value)
    except json.JSONDecodeError as exc:
        raise PlanStoreError(f"{field_name} is not valid JSON: {exc}") from exc


def _check_text_bounded(value: str, field_name: str) -> None:
    raw = value.encode("utf-8")
    if len(raw) > _MAX_TEXT_BYTES:
        raise PlanStoreError(
            f"{field_name} exceeds {_MAX_TEXT_BYTES} bytes ({len(raw)} bytes supplied)"
        )


def _encode_list(values: list[str] | None, field_name: str) -> str:
    """Serialise a list, rejecting entries that are blank or not strings."""
    if not values:
        return "[]"
    cleaned: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text:
            raise PlanStoreError(f"{field_name} must not contain empty entries")
        if text in cleaned:
            raise PlanStoreError(f"{field_name} contains duplicate entry {text!r}")
        cleaned.append(text)
    return json.dumps(cleaned)


def _decode_list(raw: str | None, field_name: str) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PlanMalformedError(f"{field_name} is not valid JSON: {exc}") from exc
    if not isinstance(parsed, list):
        raise PlanMalformedError(
            f"{field_name} expected a JSON list, got {type(parsed).__name__}"
        )
    return [str(item) for item in parsed]


def _ensure_db(conn: Any = None) -> None:
    """Apply this module's migration, plus the session schema it references."""
    from gateway import image_sessions

    def _apply(c: Any) -> None:
        image_sessions._ensure_db(c)
        c.executescript(_MIGRATION_FILE.read_text(encoding="utf-8"))

    if conn is not None:
        _apply(conn)
    else:
        with kitty_db.connect(_paths.KITTY_DB_FILE) as c:
            _apply(c)


def _row_to_plan(row: Any) -> StoredPlan:
    return StoredPlan(
        plan_id=row["plan_id"],
        session_id=row["session_id"],
        status=PlanStatus(row["status"]),
        original_prompt=row["original_prompt"],
        refined_prompt=row["refined_prompt"],
        character_id=row["character_id"],
        character_ref_path=row["character_ref_path"],
        recipe_id=row["recipe_id"],
        guidance_tags=_decode_list(row["guidance_tags_json"], "guidance_tags"),
        references=_decode_refs(row["references_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _decode_refs(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PlanMalformedError(f"references is not valid JSON: {exc}") from exc
    if not isinstance(parsed, list):
        raise PlanMalformedError(
            f"references expected a JSON list, got {type(parsed).__name__}"
        )
    return [dict(item) for item in parsed if isinstance(item, dict)]


def persist_plan(
    session_id: str,
    plan: Any,
    *,
    status: PlanStatus = PlanStatus.APPROVED,
    db_path: Any = None,
) -> StoredPlan:
    """Persist an approved ``ImagePlan`` under a stable, session-owned id.

    Raises ``PlanStoreError`` if the session does not exist or the plan cannot
    be serialised safely.
    """
    from gateway import image_sessions
    from gateway.image_sessions import ImageSessionError

    try:
        image_sessions.require_session(session_id)
    except ImageSessionError as exc:
        raise PlanStoreError(str(exc)) from exc

    plan_dict = plan.to_dict() if hasattr(plan, "to_dict") else dict(plan)
    original_prompt = str(plan_dict.get("original_prompt", "")).strip()
    refined_prompt = str(plan_dict.get("refined_prompt", "")).strip()
    if not original_prompt:
        raise PlanStoreError("cannot persist a plan with an empty original prompt")
    if not refined_prompt:
        raise PlanStoreError("cannot persist a plan with an empty refined prompt")

    _check_text_bounded(original_prompt, "original_prompt")
    _check_text_bounded(refined_prompt, "refined_prompt")

    guidance_tags = _encode_list(
        [str(t) for t in plan_dict.get("guidance_tags", [])], "guidance_tags"
    )
    references = plan_dict.get("references", [])
    references_json = json.dumps([dict(r) for r in references]) if references else "[]"
    _check_json_bounded(references_json, "references")

    now = _now_iso()
    stored = StoredPlan(
        plan_id=_new_plan_id(),
        session_id=session_id,
        status=status,
        original_prompt=original_prompt,
        refined_prompt=refined_prompt,
        character_id=plan_dict.get("character_id"),
        character_ref_path=plan_dict.get("character_ref_path"),
        recipe_id=plan_dict.get("recipe_id"),
        guidance_tags=json.loads(guidance_tags),
        references=json.loads(references_json),
        created_at=now,
        updated_at=now,
    )

    db = _paths.KITTY_DB_FILE if db_path is None else db_path
    with kitty_db.connect(db) as conn:
        _ensure_db(conn)
        conn.execute(
            "INSERT INTO image_plans"
            " (plan_id, session_id, status, original_prompt, refined_prompt,"
            "  character_id, character_ref_path, recipe_id, guidance_tags_json,"
            "  references_json, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stored.plan_id,
                stored.session_id,
                stored.status.value,
                stored.original_prompt,
                stored.refined_prompt,
                stored.character_id,
                stored.character_ref_path,
                stored.recipe_id,
                guidance_tags,
                references_json,
                stored.created_at,
                stored.updated_at,
            ),
        )
    return stored


def get_plan(plan_id: str, *, db_path: Any = None) -> StoredPlan | None:
    """Retrieve a persisted plan, or None if it does not exist."""
    if not plan_id or not plan_id.strip():
        raise PlanStoreError("plan_id must not be empty")
    db = _paths.KITTY_DB_FILE if db_path is None else db_path
    with kitty_db.connect(db) as conn:
        _ensure_db(conn)
        row = conn.execute(
            "SELECT * FROM image_plans WHERE plan_id = ?", (plan_id,)
        ).fetchone()
    return _row_to_plan(row) if row else None


def require_plan(plan_id: str, *, db_path: Any = None) -> StoredPlan:
    """Retrieve a plan, raising if it is missing or malformed."""
    plan = get_plan(plan_id, db_path=db_path)
    if plan is None:
        raise PlanNotFoundError(f"no image plan {plan_id!r}")
    return plan


def require_approved_plan(
    plan_id: str,
    session_id: str,
    *,
    db_path: Any = None,
) -> StoredPlan:
    """Load the plan a session may dispatch: owned by it and approved.

    This is the single gate A2's dispatch path calls. It fails loud on every
    way a caller can misuse a plan id: unknown, malformed, owned by a different
    session, or not approved. Rejecting here — not at render time — is what
    stops a form mutation or a leaked plan id from silently changing a render.
    """
    if not session_id or not session_id.strip():
        raise PlanStoreError("session_id must not be empty")
    plan = require_plan(plan_id, db_path=db_path)
    if plan.session_id != session_id:
        raise PlanSessionMismatchError(
            f"plan {plan_id!r} belongs to session {plan.session_id!r}, "
            f"not {session_id!r}"
        )
    if not plan.status.is_dispatchable():
        raise PlanNotApprovedError(
            f"plan {plan_id!r} is {plan.status.value}; only an approved plan can be dispatched"
        )
    return plan
