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
from gateway.image_policy import ConsentBasis, ContentLane
from gateway.paths import DB_MIGRATIONS_DIR

_MIGRATION_FILE = DB_MIGRATIONS_DIR / "030_image_plans.sql"

_MAX_JSON_BYTES = 65_536
_MAX_TEXT_BYTES = 10_240

#: Operations a persisted plan may dispatch through. An approved plan's
#: operation is what /studio/generate routes on — img2img must reach
#: image_runner.run_edit(), never image_runner.run().
ALLOWED_OPERATIONS = {"txt2img", "img2img"}

#: Accepted content lanes and consent bases, mirrored from image_policy so the
#: store can fail loud on a corrupt row instead of round-tripping it silently.
_VALID_LANES = frozenset(lane.value for lane in ContentLane)
_VALID_CONSENT = frozenset(basis.value for basis in ConsentBasis)
_DEFAULT_LANE = ContentLane.SAFE.value


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
    operation: str
    anchor_job_id: str | None = None
    guidance_tags: list[str] = field(default_factory=list)
    references: list[dict[str, Any]] = field(default_factory=list)
    intent_version: int = 0
    intent: dict[str, Any] | None = None
    # Content-lane contract (ADR 0040 #8). Defaults are the safe lane, so a
    # pre-IL-02 plan or a caller that does not opt in is never private_adult.
    content_lane: str = _DEFAULT_LANE
    consent_basis: str | None = None
    adult_confirmed: bool = False
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
            "operation": self.operation,
            "anchor_job_id": self.anchor_job_id,
            "guidance_tags": list(self.guidance_tags),
            "references": [dict(r) for r in self.references],
            "intent_version": self.intent_version,
            "intent": dict(self.intent) if self.intent is not None else None,
            "content_lane": self.content_lane,
            "consent_basis": self.consent_basis,
            "adult_confirmed": self.adult_confirmed,
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


def _ensure_plan_operation_columns(conn: Any) -> None:
    """Add image_plans.operation/anchor_job_id if absent (migration 035).

    Deferred rather than folded into 030's script: ALTER TABLE has no
    IF NOT EXISTS form in SQLite and this function must stay re-runnable, so
    it mirrors image_jobs._ensure_queue_columns and
    image_sessions._ensure_session_column.
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(image_plans)").fetchall()}
    if "operation" not in cols:
        conn.execute(
            "ALTER TABLE image_plans ADD COLUMN operation TEXT NOT NULL DEFAULT 'txt2img'"
        )
    if "anchor_job_id" not in cols:
        conn.execute("ALTER TABLE image_plans ADD COLUMN anchor_job_id TEXT")


def _ensure_plan_policy_columns(conn: Any) -> None:
    """Add image_plans content-lane columns if absent (IL-02 migration).

    Additive-only per IL-02: pre-IL-02 plans backfill to the safe lane with
    null consent and no adult confirmation — never to private_adult. Columns
    are re-runnable identically to _ensure_plan_operation_columns.
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(image_plans)").fetchall()}
    if "content_lane" not in cols:
        conn.execute(
            f"ALTER TABLE image_plans ADD COLUMN content_lane TEXT NOT NULL DEFAULT {_DEFAULT_LANE!r}"
        )
    if "consent_basis" not in cols:
        conn.execute("ALTER TABLE image_plans ADD COLUMN consent_basis TEXT")
    if "adult_confirmed" not in cols:
        conn.execute(
            "ALTER TABLE image_plans ADD COLUMN adult_confirmed INTEGER NOT NULL DEFAULT 0"
        )


def _ensure_plan_intent_columns(conn: Any) -> None:
    """Add provider-neutral ImageIntent storage without invalidating old plans."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(image_plans)").fetchall()}
    if "intent_version" not in cols:
        conn.execute("ALTER TABLE image_plans ADD COLUMN intent_version INTEGER NOT NULL DEFAULT 0")
    if "intent_json" not in cols:
        conn.execute("ALTER TABLE image_plans ADD COLUMN intent_json TEXT")


def _ensure_db(conn: Any = None) -> None:
    """Apply this module's migration, plus the session schema it references."""
    from gateway import image_sessions

    def _apply(c: Any) -> None:
        image_sessions._ensure_db(c)
        c.executescript(_MIGRATION_FILE.read_text(encoding="utf-8"))
        _ensure_plan_operation_columns(c)
        _ensure_plan_policy_columns(c)
        _ensure_plan_intent_columns(c)

    if conn is not None:
        _apply(conn)
    else:
        with kitty_db.connect(_paths.KITTY_DB_FILE) as c:
            _apply(c)


def _row_to_plan(row: Any) -> StoredPlan:
    operation = row["operation"]
    if operation not in ALLOWED_OPERATIONS:
        raise PlanMalformedError(
            f"plan {row['plan_id']!r} has unknown operation {operation!r}; "
            f"expected one of {sorted(ALLOWED_OPERATIONS)}"
        )
    anchor_job_id = row["anchor_job_id"]
    if operation == "img2img" and not anchor_job_id:
        raise PlanMalformedError(
            f"plan {row['plan_id']!r} is operation='img2img' but has no anchor_job_id"
        )
    content_lane = row["content_lane"]
    if content_lane not in _VALID_LANES:
        raise PlanMalformedError(
            f"plan {row['plan_id']!r} has unknown content_lane {content_lane!r}; "
            f"expected one of {sorted(_VALID_LANES)}"
        )
    consent_basis = row["consent_basis"]
    if consent_basis is not None and consent_basis not in _VALID_CONSENT:
        raise PlanMalformedError(
            f"plan {row['plan_id']!r} has invalid consent_basis {consent_basis!r}; "
            f"expected one of {sorted(_VALID_CONSENT)}"
        )
    adult_confirmed = bool(row["adult_confirmed"])
    if content_lane == ContentLane.PRIVATE_ADULT.value:
        if not adult_confirmed or not consent_basis:
            raise PlanMalformedError(
                f"plan {row['plan_id']!r} is content_lane='private_adult' but lacks "
                "adult_confirmed and a consent_basis; a stored plan cannot deviate "
                "toward private_adult"
            )
    return StoredPlan(
        plan_id=row["plan_id"],
        session_id=row["session_id"],
        status=PlanStatus(row["status"]),
        original_prompt=row["original_prompt"],
        refined_prompt=row["refined_prompt"],
        character_id=row["character_id"],
        character_ref_path=row["character_ref_path"],
        recipe_id=row["recipe_id"],
        operation=operation,
        anchor_job_id=anchor_job_id,
        guidance_tags=_decode_list(row["guidance_tags_json"], "guidance_tags"),
        references=_decode_refs(row["references_json"]),
        intent_version=int(row["intent_version"] or 0),
        intent=_decode_intent(row["intent_json"], int(row["intent_version"] or 0)),
        content_lane=content_lane,
        consent_basis=consent_basis,
        adult_confirmed=adult_confirmed,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _decode_intent(raw: str | None, version: int) -> dict[str, Any] | None:
    if not raw:
        if version != 0:
            raise PlanMalformedError("intent_version is set but intent_json is missing")
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PlanMalformedError(f"intent is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise PlanMalformedError("intent expected a JSON object")
    embedded = parsed.get("intent_version")
    if embedded != version or version < 1:
        raise PlanMalformedError(
            f"intent version mismatch: column={version!r}, payload={embedded!r}"
        )
    return dict(parsed)


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
    operation: str | None = None,
    anchor_job_id: str | None = None,
    db_path: Any = None,
) -> StoredPlan:
    """Persist an approved ``ImagePlan`` under a stable, session-owned id.

    *operation* and *anchor_job_id* may be passed explicitly, or carried on
    *plan* itself (``plan.to_dict()``/``dict(plan)``); an explicit argument
    wins. *operation* defaults to ``"txt2img"`` for callers that predate the
    edit-vs-generate distinction. An ``img2img`` plan must carry a non-empty
    ``anchor_job_id`` identifying the image being edited — this is the field
    ``/studio/generate`` later trusts over any mutable request body.

    Raises ``PlanStoreError`` if the session does not exist, the operation is
    not one of ``ALLOWED_OPERATIONS``, an img2img plan has no anchor, or the
    plan cannot be serialised safely.
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

    resolved_operation = operation if operation is not None else plan_dict.get(
        "operation", "txt2img"
    )
    if resolved_operation not in ALLOWED_OPERATIONS:
        raise PlanStoreError(
            f"unknown operation {resolved_operation!r}; must be one of "
            f"{sorted(ALLOWED_OPERATIONS)}"
        )

    resolved_anchor = (
        anchor_job_id if anchor_job_id is not None else plan_dict.get("anchor_job_id")
    )
    if resolved_anchor is not None:
        resolved_anchor = str(resolved_anchor).strip() or None
    if resolved_operation == "img2img" and not resolved_anchor:
        raise PlanStoreError(
            "an img2img plan requires anchor_job_id identifying the image being edited"
        )

    content_lane_value = plan_dict.get("content_lane", _DEFAULT_LANE)
    content_lane = str(content_lane_value).strip().lower()
    if content_lane not in _VALID_LANES:
        raise PlanStoreError(
            f"unknown content_lane {content_lane_value!r}; must be one of "
            f"{sorted(_VALID_LANES)}"
        )

    consent_basis_value = plan_dict.get("consent_basis")
    consent_basis: str | None = None
    if consent_basis_value is not None:
        consent_basis = str(consent_basis_value).strip().lower()
        if consent_basis not in _VALID_CONSENT:
            raise PlanStoreError(
                f"invalid consent_basis {consent_basis_value!r}; must be one of "
                f"{sorted(_VALID_CONSENT)} or null"
            )

    adult_confirmed_value = plan_dict.get("adult_confirmed", False)
    if isinstance(adult_confirmed_value, bool):
        adult_confirmed = adult_confirmed_value
    elif isinstance(adult_confirmed_value, int) and adult_confirmed_value in (0, 1):
        adult_confirmed = bool(adult_confirmed_value)
    else:
        raise PlanStoreError(
            f"adult_confirmed must be a boolean, got {adult_confirmed_value!r}"
        )

    if content_lane == ContentLane.PRIVATE_ADULT.value:
        if not adult_confirmed or not consent_basis:
            raise PlanStoreError(
                "content_lane='private_adult' requires consent_basis in "
                f"{sorted(_VALID_CONSENT)} and adult_confirmed=true at persist time; "
                "these cannot be inferred from prompt text"
            )

    guidance_tags = _encode_list(
        [str(t) for t in plan_dict.get("guidance_tags", [])], "guidance_tags"
    )
    references = plan_dict.get("references", [])
    references_json = json.dumps([dict(r) for r in references]) if references else "[]"
    _check_json_bounded(references_json, "references")

    intent_value = plan_dict.get("intent")
    intent_version = 0
    intent: dict[str, Any] | None = None
    intent_json: str | None = None
    if intent_value is not None:
        if not isinstance(intent_value, dict):
            raise PlanStoreError("intent must serialize to a JSON object")
        intent = dict(intent_value)
        raw_version = intent.get("intent_version")
        if not isinstance(raw_version, int) or raw_version < 1:
            raise PlanStoreError("intent.intent_version must be a positive integer")
        intent_version = raw_version
        expected_operation = "edit" if resolved_operation == "img2img" else "generate"
        allowed_intent_operations = {expected_operation}
        if resolved_operation == "img2img":
            allowed_intent_operations.add("variation")
        if intent.get("operation") not in allowed_intent_operations:
            if operation is not None:
                # persist_plan's explicit operation has always been authoritative;
                # keep the additive intent projection consistent with that contract.
                intent["operation"] = expected_operation
            else:
                raise PlanStoreError(
                    f"intent operation {intent.get('operation')!r} conflicts with persisted operation {resolved_operation!r}"
                )
        intent_json = json.dumps(intent, sort_keys=True, separators=(",", ":"))
        _check_json_bounded(intent_json, "intent")

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
        operation=resolved_operation,
        anchor_job_id=resolved_anchor,
        guidance_tags=json.loads(guidance_tags),
        references=json.loads(references_json),
        intent_version=intent_version,
        intent=intent,
        content_lane=content_lane,
        consent_basis=consent_basis,
        adult_confirmed=adult_confirmed,
        created_at=now,
        updated_at=now,
    )

    db = _paths.KITTY_DB_FILE if db_path is None else db_path
    with kitty_db.connect(db) as conn:
        _ensure_db(conn)
        conn.execute(
            "INSERT INTO image_plans"
            " (plan_id, session_id, status, original_prompt, refined_prompt,"
            "  character_id, character_ref_path, recipe_id, operation, anchor_job_id,"
            "  guidance_tags_json, references_json, intent_version, intent_json,"
            "  content_lane, consent_basis, adult_confirmed, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stored.plan_id,
                stored.session_id,
                stored.status.value,
                stored.original_prompt,
                stored.refined_prompt,
                stored.character_id,
                stored.character_ref_path,
                stored.recipe_id,
                stored.operation,
                stored.anchor_job_id,
                guidance_tags,
                references_json,
                stored.intent_version,
                intent_json,
                stored.content_lane,
                stored.consent_basis,
                int(stored.adult_confirmed),
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
