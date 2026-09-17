"""Durable conversational image sessions (issue #336, slice A1).

Image Studio could render an image but could not remember one. Each request
started from form state, so "keep his face, make his build broader" had nothing
to refer back to. This module stores the conversation: what the subject is,
which result is selected, what must not change, and what was asked for.

Boundaries:
- This module owns session state only. ``image_jobs`` remains the record of what
  was rendered, and ``image_runner`` remains the only dispatch path. Nothing
  here submits work to a renderer.
- The anchor is the selected result a follow-up operates on. Only a succeeded
  job carrying a verified artifact may become one — an anchor that cannot be
  fed to a renderer is worse than no anchor, because it fails at render time
  instead of selection time.
- Every mutation validates and raises. There are no silent no-ops: a session
  that quietly forgets its anchor produces a fresh reroll wearing the language
  of an edit, which is the exact failure issue #336 calls out.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from dataclasses import fields as dc_fields
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from gateway import db as kitty_db
from gateway import paths as _paths
from gateway.paths import DB_MIGRATIONS_DIR

_MIGRATION_FILE = DB_MIGRATIONS_DIR / "029_image_sessions.sql"
_PROJECTS_MIGRATION_FILE = DB_MIGRATIONS_DIR / "010_projects.sql"
_RESERVATIONS_MIGRATION_FILE = DB_MIGRATIONS_DIR / "061_image_session_reservations.sql"

_MAX_JSON_BYTES = 65_536
_MAX_TEXT_BYTES = 10_240


class ImageSessionStatus(str, Enum):
    """Lifecycle of a conversational image session."""

    ACTIVE = "active"
    ENDED = "ended"

    def is_terminal(self) -> bool:
        return self is ImageSessionStatus.ENDED


class TurnRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ImageSessionError(RuntimeError):
    """Raised when a session operation cannot complete safely."""


class SessionNotFoundError(ImageSessionError):
    """Raised when a session id does not exist."""


class SessionEndedError(ImageSessionError):
    """Raised when a mutation targets an already-ended session."""


class AnchorError(ImageSessionError):
    """Raised when a job cannot serve as an anchor."""


class SessionBudgetExceededError(ImageSessionError):
    """Raised before dispatch when a render would exceed a session ceiling."""


@dataclass
class ImageSession:
    session_id: str
    status: ImageSessionStatus
    title: str | None
    project_id: int | None
    character_id: str | None
    reference_ids_json: str | None
    anchor_job_id: str | None
    anchor_artifact_id: str | None
    protected_traits_json: str | None
    requested_changes_json: str | None
    last_plan_json: str | None
    spend_usd: float
    reserved_spend_usd: float
    attempt_count: int
    created_at: str
    updated_at: str
    ended_at: str | None

    @property
    def reference_ids(self) -> list[str]:
        return _decode_list(self.reference_ids_json)

    @property
    def protected_traits(self) -> list[str]:
        return _decode_list(self.protected_traits_json)

    @property
    def requested_changes(self) -> list[str]:
        return _decode_list(self.requested_changes_json)

    @property
    def last_plan(self) -> dict[str, Any] | None:
        if not self.last_plan_json:
            return None
        return json.loads(self.last_plan_json)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for fld in self.__dataclass_fields__:
            val = getattr(self, fld)
            if isinstance(val, Enum):
                val = val.value
            result[fld] = val
        result["reference_ids"] = self.reference_ids
        result["protected_traits"] = self.protected_traits
        result["requested_changes"] = self.requested_changes
        return result


@dataclass
class SessionTurn:
    turn_id: str
    session_id: str
    seq: int
    role: TurnRole
    content: str | None
    job_id: str | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "session_id": self.session_id,
            "seq": self.seq,
            "role": self.role.value,
            "content": self.content,
            "job_id": self.job_id,
            "created_at": self.created_at,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_session_id() -> str:
    return f"imgses_{uuid.uuid4().hex}"


def _new_turn_id() -> str:
    return f"turn_{uuid.uuid4().hex}"


def _decode_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ImageSessionError(f"expected a JSON list, got {type(parsed).__name__}")
    return [str(item) for item in parsed]


def _encode_list(values: list[str] | None, field_name: str) -> str | None:
    """Serialise a string list, rejecting blanks and duplicates."""
    if values is None:
        return None
    seen: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text:
            raise ImageSessionError(f"{field_name} must not contain empty entries")
        if text in seen:
            raise ImageSessionError(f"{field_name} contains duplicate entry {text!r}")
        seen.append(text)
    encoded = json.dumps(seen)
    _check_json_bounded(encoded, field_name)
    return encoded


def _check_json_bounded(value: str | None, field_name: str) -> None:
    if value is None:
        return
    raw = value.encode("utf-8")
    if len(raw) > _MAX_JSON_BYTES:
        raise ImageSessionError(
            f"{field_name} exceeds {_MAX_JSON_BYTES} bytes ({len(raw)} bytes supplied)"
        )
    try:
        json.loads(value)
    except json.JSONDecodeError as exc:
        raise ImageSessionError(f"{field_name} is not valid JSON: {exc}") from exc


def _check_text_bounded(value: str | None, field_name: str) -> None:
    if value is None:
        return
    raw = value.encode("utf-8")
    if len(raw) > _MAX_TEXT_BYTES:
        raise ImageSessionError(
            f"{field_name} exceeds {_MAX_TEXT_BYTES} bytes ({len(raw)} bytes supplied)"
        )


def _ensure_session_column(conn: Any) -> None:
    """Add image_jobs.session_id if absent.

    Deferred rather than written into the .sql file because ALTER TABLE has no
    IF NOT EXISTS form in SQLite, and the migration must stay re-runnable — the
    same pattern image_jobs._ensure_queue_columns uses.

    Deliberately unguarded: callers reach this only after image_jobs._ensure_db
    has created the table, so a failing PRAGMA means the schema is broken.
    Swallowing it would skip the column and surface later as an inscrutable
    "no such column: session_id" on the first insert.
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(image_jobs)").fetchall()}
    if "session_id" not in cols:
        conn.execute("ALTER TABLE image_jobs ADD COLUMN session_id TEXT")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_image_jobs_session ON image_jobs(session_id)"
    )


def _ensure_spend_columns(conn: Any) -> None:
    """Add the unsettled paid-exposure column to image sessions.

    ``spend_usd`` is settled spend only. ``reserved_spend_usd`` is conservative
    pre-dispatch exposure that still counts against the budget until it is
    released or reconciled. SQLite cannot add this column idempotently in SQL,
    so the versioned migration is a marker and this helper owns the ALTER.
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(image_sessions)").fetchall()}
    if "reserved_spend_usd" not in cols:
        conn.execute(
            "ALTER TABLE image_sessions ADD COLUMN reserved_spend_usd REAL NOT NULL DEFAULT 0"
        )


def _ensure_project_column(conn: Any) -> None:
    """Add optional Project scope to image sessions.

    The projects table is an explicit dependency once a creative session can be
    project-scoped. The FK makes nonexistent project IDs fail closed instead of
    becoming dangling provenance.
    """
    conn.executescript(_PROJECTS_MIGRATION_FILE.read_text(encoding="utf-8"))
    cols = {row[1] for row in conn.execute("PRAGMA table_info(image_sessions)").fetchall()}
    if "project_id" not in cols:
        conn.execute(
            "ALTER TABLE image_sessions ADD COLUMN project_id INTEGER REFERENCES projects(id)"
        )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_image_sessions_project "
        "ON image_sessions(project_id, updated_at DESC)"
    )


def _backfill_legacy_reservations(conn: Any) -> None:
    """Carry pre-ledger aggregate exposure into per-reservation rows.

    A database upgraded mid-flight must not silently forget a reservation that
    is still counted against a session's budget. ``_ensure_db`` replays its
    migrations on every call, so the "no rows for this session yet" guard is
    part of the statement: a replay can never duplicate a session's exposure.
    """
    conn.execute(
        """
        INSERT INTO image_session_reservations
            (reservation_id, session_id, job_id, cost_usd, state, created_at, updated_at)
        SELECT 'legacy_' || session_id, session_id, NULL, reserved_spend_usd, 'reserved',
               updated_at, updated_at
          FROM image_sessions
         WHERE reserved_spend_usd > 0
           AND NOT EXISTS (
               SELECT 1 FROM image_session_reservations existing
                WHERE existing.session_id = image_sessions.session_id
           )
        """
    )


def _ensure_db(conn: Any = None) -> None:
    """Apply this module's migration, plus the schemas it references."""
    def _apply(c: Any) -> None:
        from gateway import image_jobs

        image_jobs._ensure_db(c)
        c.executescript(_MIGRATION_FILE.read_text(encoding="utf-8"))
        _ensure_session_column(c)
        _ensure_spend_columns(c)
        _ensure_project_column(c)
        # After the columns it reads exist: the reservations DDL is replayed
        # on every call, and the backfill needs `reserved_spend_usd`.
        c.executescript(_RESERVATIONS_MIGRATION_FILE.read_text(encoding="utf-8"))
        _backfill_legacy_reservations(c)
        # The INSERT above opens an implicit transaction on the caller's
        # connection; leave it clean so the next BEGIN IMMEDIATE is legal.
        c.commit()

    if conn is not None:
        _apply(conn)
    else:
        with kitty_db.connect(_paths.KITTY_DB_FILE) as c:
            _apply(c)


def _row_to_session(row: Any) -> ImageSession:
    return ImageSession(
        session_id=row["session_id"],
        status=ImageSessionStatus(row["status"]),
        title=row["title"],
        project_id=row["project_id"],
        character_id=row["character_id"],
        reference_ids_json=row["reference_ids_json"],
        anchor_job_id=row["anchor_job_id"],
        anchor_artifact_id=row["anchor_artifact_id"],
        protected_traits_json=row["protected_traits_json"],
        requested_changes_json=row["requested_changes_json"],
        last_plan_json=row["last_plan_json"],
        spend_usd=row["spend_usd"] if row["spend_usd"] is not None else 0.0,
        reserved_spend_usd=(
            row["reserved_spend_usd"] if row["reserved_spend_usd"] is not None else 0.0
        ),
        attempt_count=row["attempt_count"] if row["attempt_count"] is not None else 0,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        ended_at=row["ended_at"],
    )


def _row_to_turn(row: Any) -> SessionTurn:
    return SessionTurn(
        turn_id=row["turn_id"],
        session_id=row["session_id"],
        seq=row["seq"],
        role=TurnRole(row["role"]),
        content=row["content"],
        job_id=row["job_id"],
        created_at=row["created_at"],
    )


def create_session(
    *,
    title: str | None = None,
    project_id: int | None = None,
    character_id: str | None = None,
    reference_ids: list[str] | None = None,
    protected_traits: list[str] | None = None,
) -> ImageSession:
    """Open a new conversational image session."""
    _check_text_bounded(title, "title")
    if project_id is not None and (isinstance(project_id, bool) or project_id <= 0):
        raise ImageSessionError(f"project_id must be a positive integer, got {project_id!r}")
    session = ImageSession(
        session_id=_new_session_id(),
        status=ImageSessionStatus.ACTIVE,
        title=title,
        project_id=project_id,
        character_id=character_id,
        reference_ids_json=_encode_list(reference_ids, "reference_ids"),
        anchor_job_id=None,
        anchor_artifact_id=None,
        protected_traits_json=_encode_list(protected_traits, "protected_traits"),
        requested_changes_json=None,
        last_plan_json=None,
        spend_usd=0.0,
        reserved_spend_usd=0.0,
        attempt_count=0,
        created_at=_now_iso(),
        updated_at=_now_iso(),
        ended_at=None,
    )
    field_names = [f.name for f in dc_fields(session)]
    columns_sql = ", ".join(field_names)
    placeholders = ", ".join(["?"] * len(field_names))
    values = tuple(
        getattr(session, f).value if f == "status" else getattr(session, f)
        for f in field_names
    )
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        try:
            conn.execute(
                f"INSERT INTO image_sessions ({columns_sql}) VALUES ({placeholders})",
                values,
            )
        except sqlite3.IntegrityError as exc:
            if project_id is not None and "FOREIGN KEY" in str(exc).upper():
                raise ImageSessionError(
                    f"project {project_id} does not exist; refusing dangling image-session scope"
                ) from exc
            raise
    return session


def get_session(session_id: str) -> ImageSession | None:
    """Retrieve a session, or None if it does not exist."""
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        row = conn.execute(
            "SELECT * FROM image_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
    return _row_to_session(row) if row else None


def require_session(session_id: str) -> ImageSession:
    """Retrieve a session, raising if it is missing."""
    session = get_session(session_id)
    if session is None:
        raise SessionNotFoundError(f"no image session {session_id!r}")
    return session


def _require_active(session_id: str) -> ImageSession:
    session = require_session(session_id)
    if session.status.is_terminal():
        raise SessionEndedError(
            f"session {session_id!r} ended at {session.ended_at}; reopen a new session"
        )
    return session


def list_sessions(
    limit: int = 50, *, status: ImageSessionStatus | None = None
) -> list[ImageSession]:
    """Most-recently-updated sessions first."""
    sql = "SELECT * FROM image_sessions"
    params: list[Any] = []
    if status is not None:
        sql += " WHERE status = ?"
        params.append(status.value)
    sql += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [_row_to_session(r) for r in rows]


def append_turn(
    session_id: str,
    role: TurnRole | str,
    content: str | None = None,
    *,
    job_id: str | None = None,
) -> SessionTurn:
    """Append a conversation turn. Sequence numbers are assigned here, not by callers."""
    role = TurnRole(role)
    _check_text_bounded(content, "content")
    _require_active(session_id)

    now = _now_iso()
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        if job_id is not None:
            job_row = conn.execute(
                "SELECT job_id FROM image_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if job_row is None:
                raise ImageSessionError(f"no image job {job_id!r} to attach to this turn")
        row = conn.execute(
            "SELECT COALESCE(MAX(seq), 0) AS max_seq FROM image_session_turns"
            " WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        turn = SessionTurn(
            turn_id=_new_turn_id(),
            session_id=session_id,
            seq=int(row["max_seq"]) + 1,
            role=role,
            content=content,
            job_id=job_id,
            created_at=now,
        )
        conn.execute(
            "INSERT INTO image_session_turns"
            " (turn_id, session_id, seq, role, content, job_id, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                turn.turn_id,
                turn.session_id,
                turn.seq,
                turn.role.value,
                turn.content,
                turn.job_id,
                turn.created_at,
            ),
        )
        conn.execute(
            "UPDATE image_sessions SET updated_at = ? WHERE session_id = ?",
            (now, session_id),
        )
    return turn


def list_turns(session_id: str, limit: int = 200) -> list[SessionTurn]:
    """Turns in conversation order. This is what resume replays."""
    require_session(session_id)
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        rows = conn.execute(
            "SELECT * FROM image_session_turns WHERE session_id = ?"
            " ORDER BY seq ASC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    return [_row_to_turn(r) for r in rows]


def attach_job(session_id: str, job_id: str) -> None:
    """Record that a job belongs to this session."""
    _require_active(session_id)
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        cur = conn.execute(
            "UPDATE image_jobs SET session_id = ? WHERE job_id = ?",
            (session_id, job_id),
        )
        if cur.rowcount == 0:
            raise ImageSessionError(f"no image job {job_id!r} to attach to session")


def list_session_jobs(session_id: str, limit: int = 200) -> list[Any]:
    """Jobs produced by this session, oldest first."""
    from gateway import image_jobs

    require_session(session_id)
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        rows = conn.execute(
            "SELECT * FROM image_jobs WHERE session_id = ?"
            " ORDER BY created_at ASC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    return [image_jobs._row_to_job(r) for r in rows]


def job_session_id(job_id: str) -> str | None:
    """Return the session a job is attached to, or None.

    Exposes the ``image_jobs.session_id`` link (added by
    ``_ensure_session_column``) so callers can resolve the character identity a
    rendered job was produced under without inventing a second ownership model.
    """
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        row = conn.execute(
            "SELECT session_id FROM image_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
    return row["session_id"] if row else None


def set_anchor(session_id: str, job_id: str) -> ImageSession:
    """Select a rendered result as the anchor for follow-up edits.

    Rejects any job that could not actually be fed to a renderer. Catching that
    here means "use this one" fails at selection time with a clear reason,
    rather than at render time as a mysterious reroll.
    """
    from gateway.image_jobs import ImageJobStatus

    _require_active(session_id)
    now = _now_iso()
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        row = conn.execute(
            "SELECT job_id, session_id, status, artifact_id, canonical_artifact_id, output_path FROM image_jobs"
            " WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            raise AnchorError(f"no image job {job_id!r}")
        owner_session_id = row["session_id"]
        if owner_session_id is not None and owner_session_id != session_id:
            raise AnchorError(
                f"job {job_id!r} does not belong to session {session_id!r}"
            )
        status = ImageJobStatus(row["status"])
        if status is not ImageJobStatus.SUCCEEDED:
            raise AnchorError(
                f"job {job_id!r} is {status.value}; only a succeeded job can be an anchor"
            )
        if not row["output_path"]:
            raise AnchorError(
                f"job {job_id!r} succeeded but has no verified artifact to edit from"
            )
        conn.execute(
            "UPDATE image_sessions SET anchor_job_id = ?, anchor_artifact_id = ?,"
            " updated_at = ? WHERE session_id = ?",
            (job_id, row["canonical_artifact_id"] or row["artifact_id"], now, session_id),
        )
    return require_session(session_id)


def clear_anchor(session_id: str) -> ImageSession:
    """Drop the current anchor, returning the session to fresh generation."""
    _require_active(session_id)
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        conn.execute(
            "UPDATE image_sessions SET anchor_job_id = NULL, anchor_artifact_id = NULL,"
            " updated_at = ? WHERE session_id = ?",
            (_now_iso(), session_id),
        )
    return require_session(session_id)


def update_session(
    session_id: str,
    *,
    title: str | None = None,
    character_id: str | None = None,
    reference_ids: list[str] | None = None,
    protected_traits: list[str] | None = None,
    requested_changes: list[str] | None = None,
    last_plan: dict[str, Any] | None = None,
    clear_character: bool | None = None,
) -> ImageSession:
    """Update session context. Only supplied fields change."""
    _require_active(session_id)

    updates: dict[str, Any] = {}
    if title is not None:
        _check_text_bounded(title, "title")
        updates["title"] = title
    if clear_character:
        updates["character_id"] = None
    elif character_id is not None:
        updates["character_id"] = character_id
    if reference_ids is not None:
        updates["reference_ids_json"] = _encode_list(reference_ids, "reference_ids")
    if protected_traits is not None:
        updates["protected_traits_json"] = _encode_list(
            protected_traits, "protected_traits"
        )
    if requested_changes is not None:
        updates["requested_changes_json"] = _encode_list(
            requested_changes, "requested_changes"
        )
    if last_plan is not None:
        if not isinstance(last_plan, dict):
            raise ImageSessionError(
                f"last_plan must be a dict, got {type(last_plan).__name__}"
            )
        encoded = json.dumps(last_plan)
        _check_json_bounded(encoded, "last_plan")
        updates["last_plan_json"] = encoded

    if not updates:
        raise ImageSessionError("update_session called with nothing to update")

    updates["updated_at"] = _now_iso()
    set_sql = ", ".join(f"{k} = ?" for k in updates)
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        conn.execute(
            f"UPDATE image_sessions SET {set_sql} WHERE session_id = ?",
            (*updates.values(), session_id),
        )
    return require_session(session_id)


RESERVATION_STALE_AFTER_SECONDS = 600
"""How long a reservation that never reached a dispatch may sit before it is
treated as abandoned: the caller crashed between ``reserve_attempt`` and the
provider call, so nothing can ever come back to settle it."""

RESERVATION_JOB_GRACE_SECONDS = 1_800
"""How long a dispatch-bound reservation may stay un-settled while its job is
still submitted/running/unknown. Must exceed
``image_runner._BFL_POLL_DEADLINE_SECONDS`` (900s): a legitimate BFL render
polls the provider that long, and its exposure has to keep counting against
the session budget the whole time. Recovery then gets a further window."""


@dataclass(frozen=True)
class SessionReservation:
    """A reserved paid attempt plus the identity its settlement requires.

    ``ImageSession.reserved_spend_usd`` stays the materialized session total;
    this handle is what ``reconcile_reserved_attempt_cost`` and
    ``release_reserved_attempt_cost`` take, so settling one attempt can never
    subtract another attempt's exposure.
    """

    session: ImageSession
    reservation_id: str
    cost_usd: float


def _outstanding_reservations(conn: Any, session_id: str) -> list[Any]:
    return conn.execute(
        "SELECT reservation_id, job_id, cost_usd, created_at, updated_at "
        "FROM image_session_reservations "
        "WHERE session_id = ? AND state = 'reserved'",
        (session_id,),
    ).fetchall()


def _reservation_age_seconds(row: Any, now: datetime) -> float:
    stamp = row["updated_at"] or row["created_at"]
    try:
        touched = datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return 0.0
    if touched.tzinfo is None:
        touched = touched.replace(tzinfo=timezone.utc)
    return (now - touched).total_seconds()


def _reservation_is_abandoned(conn: Any, row: Any, *, now: datetime) -> bool:
    """Judge one reservation against its owning dispatch, never the session clock.

    A session-wide timestamp cannot distinguish "the caller crashed" from "the
    provider is still working": a live BFL job may poll for 900s without
    touching the session at all.
    """
    age = _reservation_age_seconds(row, now)
    job_id = row["job_id"]
    if not job_id:
        # Never dispatched, so no provider charge can materialize.
        return age > RESERVATION_STALE_AFTER_SECONDS
    job = conn.execute(
        "SELECT status FROM image_jobs WHERE job_id = ?", (job_id,)
    ).fetchone()
    if job is None:
        return age > RESERVATION_STALE_AFTER_SECONDS
    status = str(job["status"] or "")
    if status in {"failed", "cancelled"}:
        return True
    if status == "succeeded":
        # A real charge exists. Only an explicit settle may drop it, or a
        # crashed settlement would silently forget money the provider billed.
        return False
    # submitted / running / unknown: still billable. Hold the exposure across
    # the provider polling + recovery window.
    return age > RESERVATION_JOB_GRACE_SECONDS


def _sweep_stale_reservations(conn: Any, session_id: str) -> float:
    """Abandon only genuinely abandoned reservations; return the live total.

    The session-wide ``reserved_spend_usd`` column is then reconciled to the
    sum of the rows that are still live, so a total can never outlive the
    reservation that justified it.
    """
    now = datetime.now(timezone.utc)
    live = 0.0
    for row in _outstanding_reservations(conn, session_id):
        if _reservation_is_abandoned(conn, row, now=now):
            conn.execute(
                "UPDATE image_session_reservations "
                "SET state = 'abandoned', updated_at = ? "
                "WHERE reservation_id = ? AND state = 'reserved'",
                (_now_iso(), row["reservation_id"]),
            )
            continue
        live += float(row["cost_usd"] or 0.0)
    return live


def _claim_outstanding_reservation(
    conn: Any, session_id: str, reservation_id: str, *, settlement: str
) -> float:
    """Transition one outstanding reservation to *settlement* and return its cost."""
    row = conn.execute(
        "SELECT reservation_id, cost_usd, state FROM image_session_reservations "
        "WHERE reservation_id = ? AND session_id = ?",
        (reservation_id, session_id),
    ).fetchone()
    if row is None:
        raise ImageSessionError(
            f"no reservation {reservation_id!r} for session {session_id!r}"
        )
    if row["state"] != "reserved":
        raise ImageSessionError(
            f"reservation {reservation_id!r} is {row['state']!r}, not outstanding"
        )
    conn.execute(
        "UPDATE image_session_reservations SET state = ?, updated_at = ? "
        "WHERE reservation_id = ? AND state = 'reserved'",
        (settlement, _now_iso(), reservation_id),
    )
    return float(row["cost_usd"] or 0.0)


def _reserved_total(conn: Any, session_id: str) -> float:
    row = conn.execute(
        "SELECT reserved_spend_usd FROM image_sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    if row is None:
        raise SessionNotFoundError(f"no image session {session_id!r}")
    return float(row["reserved_spend_usd"] or 0.0)


def bind_reservation_to_job(
    session_id: str, reservation_id: str, job_id: str
) -> None:
    """Tie a reservation to the dispatch it paid for, before the provider call.

    The job id is the durable identity a later recovery uses to settle this
    attempt without guessing by amount.
    """
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            "UPDATE image_session_reservations SET job_id = ?, updated_at = ? "
            "WHERE reservation_id = ? AND session_id = ? AND state = 'reserved'",
            (job_id, _now_iso(), reservation_id, session_id),
        )
        if cursor.rowcount != 1:
            raise ImageSessionError(
                f"reservation {reservation_id!r} for session {session_id!r} "
                "is not outstanding and cannot be bound to a dispatch"
            )
        conn.commit()


def reserve_attempt(
    session_id: str,
    *,
    cost_usd: float,
    max_attempts: int,
    max_spend_usd: float,
) -> SessionReservation:
    """Atomically reserve one render attempt before a paid provider is called.

    Returns the handle whose ``reservation_id`` settles this attempt and no
    other. Admission counts only live reservations: one abandoned row can no
    longer erase a concurrent attempt's exposure, and one settled attempt can
    no longer consume another's.
    """
    if cost_usd < 0:
        raise ImageSessionError(f"cost_usd must not be negative, got {cost_usd}")
    if max_attempts <= 0:
        raise ImageSessionError(f"max_attempts must be positive, got {max_attempts}")
    if max_spend_usd < 0:
        raise ImageSessionError(
            f"max_spend_usd must not be negative, got {max_spend_usd}"
        )

    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT status, attempt_count, spend_usd, reserved_spend_usd, updated_at "
            "FROM image_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            raise SessionNotFoundError(f"no image session {session_id!r}")
        if ImageSessionStatus(row["status"]).is_terminal():
            raise SessionEndedError(f"session {session_id!r} has ended")
        attempts = int(row["attempt_count"] or 0)
        spend = float(row["spend_usd"] or 0.0)
        reserved = _sweep_stale_reservations(conn, session_id)
        if attempts >= max_attempts:
            raise SessionBudgetExceededError(
                f"session {session_id!r} has used {attempts} of "
                f"{max_attempts} allowed attempts; generate refused"
            )
        projected = spend + reserved + cost_usd
        if projected > max_spend_usd + 1e-12:
            raise SessionBudgetExceededError(
                f"session {session_id!r} would spend ${projected:.3f}, above its "
                f"${max_spend_usd:.2f} allowance; generate refused"
            )
        reservation_id = f"res_{uuid.uuid4().hex}"
        now = _now_iso()
        conn.execute(
            "INSERT INTO image_session_reservations "
            "(reservation_id, session_id, job_id, cost_usd, state, created_at, updated_at) "
            "VALUES (?, ?, NULL, ?, 'reserved', ?, ?)",
            (reservation_id, session_id, cost_usd, now, now),
        )
        conn.execute(
            "UPDATE image_sessions SET attempt_count = attempt_count + 1, "
            "reserved_spend_usd = ?, updated_at = ? WHERE session_id = ?",
            (reserved + cost_usd, now, session_id),
        )
        conn.commit()
    return SessionReservation(
        session=require_session(session_id),
        reservation_id=reservation_id,
        cost_usd=cost_usd,
    )


def reconcile_reserved_attempt_cost(
    session_id: str,
    *,
    reservation_id: str,
    actual_cost_usd: float,
) -> ImageSession:
    """Replace one identified conservative reservation with provider-reported cost."""
    if actual_cost_usd < 0:
        raise ImageSessionError("actual cost must not be negative")

    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        conn.execute("BEGIN IMMEDIATE")
        reserved_cost = _claim_outstanding_reservation(
            conn, session_id, reservation_id, settlement="settled"
        )
        reserved = _reserved_total(conn, session_id)
        if reserved + 1e-12 < reserved_cost:
            raise ImageSessionError(
                f"session {session_id!r} reserved exposure ${reserved:.3f} is below the "
                f"${reserved_cost:.3f} reservation being reconciled"
            )
        conn.execute(
            "UPDATE image_sessions SET reserved_spend_usd = reserved_spend_usd - ?, "
            "spend_usd = spend_usd + ?, updated_at = ? WHERE session_id = ?",
            (reserved_cost, actual_cost_usd, _now_iso(), session_id),
        )
        conn.commit()
    return require_session(session_id)


def release_reserved_attempt_cost(
    session_id: str, *, reservation_id: str
) -> ImageSession:
    """Release one identified reservation when dispatch is known not to have happened."""
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        conn.execute("BEGIN IMMEDIATE")
        reserved_cost = _claim_outstanding_reservation(
            conn, session_id, reservation_id, settlement="released"
        )
        reserved = _reserved_total(conn, session_id)
        if reserved + 1e-12 < reserved_cost:
            raise ImageSessionError(
                f"session {session_id!r} reserved exposure ${reserved:.3f} is below the "
                f"${reserved_cost:.3f} reservation being released"
            )
        conn.execute(
            "UPDATE image_sessions SET reserved_spend_usd = reserved_spend_usd - ?, "
            "updated_at = ? WHERE session_id = ?",
            (reserved_cost, _now_iso(), session_id),
        )
        conn.commit()
    return require_session(session_id)


def finalize_recovered_paid_job(
    session_id: str,
    job_id: str,
    *,
    reserved_cost_usd: float,
    actual_cost_usd: float,
) -> ImageSession:
    """Atomically settle one recovered paid attempt and mark its artifact successful."""
    if reserved_cost_usd < 0 or actual_cost_usd < 0:
        raise ImageSessionError("recovered paid costs must not be negative")

    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        conn.execute("BEGIN IMMEDIATE")
        job = conn.execute(
            "SELECT session_id, status, output_path, canonical_artifact_id "
            "FROM image_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if job is None:
            raise ImageSessionError(f"no image job {job_id!r} to finalize")
        if job["session_id"] != session_id:
            raise ImageSessionError(
                f"job {job_id!r} does not belong to session {session_id!r}"
            )
        if job["status"] != "unknown":
            raise ImageSessionError(
                f"job {job_id!r} is {job['status']!r}; only unknown jobs can be recovered"
            )
        if not job["output_path"] or not job["canonical_artifact_id"]:
            raise ImageSessionError(
                f"job {job_id!r} cannot be finalized before canonical artifact commit"
            )
        reservation = conn.execute(
            "SELECT reservation_id, cost_usd FROM image_session_reservations "
            "WHERE job_id = ? AND session_id = ? AND state = 'reserved' "
            "ORDER BY created_at ASC, rowid ASC LIMIT 1",
            (job_id, session_id),
        ).fetchone()
        if reservation is None:
            # Receipts written before reservations were dispatch-bound carry
            # only the amount. Match the session's oldest outstanding
            # reservation and refuse on any mismatch rather than settling a
            # different attempt's exposure.
            reservation = conn.execute(
                "SELECT reservation_id, cost_usd FROM image_session_reservations "
                "WHERE session_id = ? AND job_id IS NULL AND state = 'reserved' "
                "ORDER BY created_at ASC, rowid ASC LIMIT 1",
                (session_id,),
            ).fetchone()
        if reservation is None:
            raise ImageSessionError(
                f"no outstanding reservation for job {job_id!r} in session {session_id!r}"
            )
        held = float(reservation["cost_usd"] or 0.0)
        if abs(held - reserved_cost_usd) > 1e-9:
            raise ImageSessionError(
                f"job {job_id!r} carries a ${reserved_cost_usd:.3f} reserved receipt but "
                f"reservation {reservation['reservation_id']!r} holds ${held:.3f}; "
                "refusing to settle a different attempt"
            )
        reserved_cost = _claim_outstanding_reservation(
            conn, session_id, str(reservation["reservation_id"]), settlement="settled"
        )
        reserved = _reserved_total(conn, session_id)
        if reserved + 1e-12 < reserved_cost:
            raise ImageSessionError(
                f"session {session_id!r} reserved exposure ${reserved:.3f} is below the "
                f"${reserved_cost:.3f} recovered reservation"
            )
        now = _now_iso()
        conn.execute(
            "UPDATE image_sessions SET reserved_spend_usd = reserved_spend_usd - ?, "
            "spend_usd = spend_usd + ?, updated_at = ? WHERE session_id = ?",
            (reserved_cost, actual_cost_usd, now, session_id),
        )
        conn.execute(
            "UPDATE image_jobs SET status = 'succeeded', normalized_error = NULL, "
            "updated_at = ?, finished_at = ? WHERE job_id = ?",
            (now, now, job_id),
        )
        conn.commit()
    return require_session(session_id)


def record_attempt(session_id: str, *, cost_usd: float = 0.0) -> ImageSession:
    """Count one completed render attempt and add its cost to the session total."""
    if cost_usd < 0:
        raise ImageSessionError(f"cost_usd must not be negative, got {cost_usd}")
    _require_active(session_id)
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        conn.execute(
            "UPDATE image_sessions SET attempt_count = attempt_count + 1,"
            " spend_usd = spend_usd + ?, updated_at = ? WHERE session_id = ?",
            (cost_usd, _now_iso(), session_id),
        )
    return require_session(session_id)


def end_session(session_id: str) -> ImageSession:
    """Close a session. Ending an already-ended session is an error, not a no-op."""
    _require_active(session_id)
    now = _now_iso()
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        conn.execute(
            "UPDATE image_sessions SET status = ?, ended_at = ?, updated_at = ?"
            " WHERE session_id = ?",
            (ImageSessionStatus.ENDED.value, now, now, session_id),
        )
    return require_session(session_id)
