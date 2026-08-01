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


@dataclass
class ImageSession:
    session_id: str
    status: ImageSessionStatus
    title: str | None
    character_id: str | None
    reference_ids_json: str | None
    anchor_job_id: str | None
    anchor_artifact_id: str | None
    protected_traits_json: str | None
    requested_changes_json: str | None
    last_plan_json: str | None
    spend_usd: float
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


def _ensure_db(conn: Any = None) -> None:
    """Apply this module's migration, plus the image_jobs schema it references."""
    def _apply(c: Any) -> None:
        from gateway import image_jobs

        image_jobs._ensure_db(c)
        c.executescript(_MIGRATION_FILE.read_text(encoding="utf-8"))
        _ensure_session_column(c)

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
        character_id=row["character_id"],
        reference_ids_json=row["reference_ids_json"],
        anchor_job_id=row["anchor_job_id"],
        anchor_artifact_id=row["anchor_artifact_id"],
        protected_traits_json=row["protected_traits_json"],
        requested_changes_json=row["requested_changes_json"],
        last_plan_json=row["last_plan_json"],
        spend_usd=row["spend_usd"] if row["spend_usd"] is not None else 0.0,
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
    character_id: str | None = None,
    reference_ids: list[str] | None = None,
    protected_traits: list[str] | None = None,
) -> ImageSession:
    """Open a new conversational image session."""
    _check_text_bounded(title, "title")
    session = ImageSession(
        session_id=_new_session_id(),
        status=ImageSessionStatus.ACTIVE,
        title=title,
        character_id=character_id,
        reference_ids_json=_encode_list(reference_ids, "reference_ids"),
        anchor_job_id=None,
        anchor_artifact_id=None,
        protected_traits_json=_encode_list(protected_traits, "protected_traits"),
        requested_changes_json=None,
        last_plan_json=None,
        spend_usd=0.0,
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
        conn.execute(
            f"INSERT INTO image_sessions ({columns_sql}) VALUES ({placeholders})",
            values,
        )
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
            "SELECT job_id, status, artifact_id, output_path FROM image_jobs"
            " WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            raise AnchorError(f"no image job {job_id!r}")
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
            (job_id, row["artifact_id"], now, session_id),
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
) -> ImageSession:
    """Update session context. Only supplied fields change."""
    _require_active(session_id)

    updates: dict[str, Any] = {}
    if title is not None:
        _check_text_bounded(title, "title")
        updates["title"] = title
    if character_id is not None:
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


def record_attempt(session_id: str, *, cost_usd: float = 0.0) -> ImageSession:
    """Count one render attempt and add its cost to the session total."""
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
