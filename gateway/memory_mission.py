"""Gateway-owned durable Mission state for Mission Center.

Mission state lives in Kitty's existing application SQLite database. It owns
outcome-level continuity only; Builder, GAR, KX, automations, and providers keep
their existing authoritative state.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from gateway import builder_initiative as bi
from gateway import db as kitty_db
from gateway.paths import KITTY_DB_FILE

MISSION_DB_FILE = KITTY_DB_FILE


class MissionError(RuntimeError):
    """Base Mission state error."""


class MissionNotFound(MissionError):
    """Raised when a Mission id has no durable row."""


_UNSET = object()


def init_db(*, db_path: Path = MISSION_DB_FILE) -> None:
    """Create additive Mission tables in Kitty's existing app database."""
    with kitty_db.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS missions (
                mission_id TEXT PRIMARY KEY,
                objective TEXT NOT NULL,
                definition_of_done_json TEXT NOT NULL,
                status TEXT NOT NULL,
                status_reason TEXT,
                paused_from_status TEXT,
                supervisor_id TEXT NOT NULL,
                supervisor_epoch INTEGER NOT NULL,
                plan_ref TEXT,
                plan_digest TEXT,
                plan_review_state TEXT NOT NULL DEFAULT 'unreviewed',
                plan_reviewer_id TEXT,
                plan_review_evidence_json TEXT,
                plan_payload_json TEXT,
                builder_locator_json TEXT,
                checkpoint_json TEXT NOT NULL DEFAULT '{}',
                source_cursors_json TEXT NOT NULL DEFAULT '{}',
                last_cycle_json TEXT,
                pending_escalation_json TEXT,
                candidate_ref TEXT,
                candidate_digest TEXT,
                acceptance_state TEXT NOT NULL DEFAULT 'unreviewed',
                acceptance_reviewer_id TEXT,
                acceptance_evidence_json TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS mission_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mission_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                supervisor_epoch INTEGER,
                payload_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY(mission_id) REFERENCES missions(mission_id)
            );
            CREATE INDEX IF NOT EXISTS idx_mission_events_mission
                ON mission_events(mission_id, id);
            """
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(missions)")}
        if "paused_from_status" not in columns:
            conn.execute("ALTER TABLE missions ADD COLUMN paused_from_status TEXT")
        if "builder_locator_json" not in columns:
            conn.execute("ALTER TABLE missions ADD COLUMN builder_locator_json TEXT")
        if "plan_payload_json" not in columns:
            conn.execute("ALTER TABLE missions ADD COLUMN plan_payload_json TEXT")
        # Where the request came from, so a delegated result can find its way
        # back without the browser holding the only copy of that relationship.
        for column, sql_type in (
            ("origin_kind", "TEXT"),
            ("origin_conversation_id", "TEXT"),
            ("origin_message_id", "TEXT"),
            ("origin_project_id", "INTEGER"),
        ):
            if column not in columns:
                conn.execute(f"ALTER TABLE missions ADD COLUMN {column} {sql_type}")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_missions_origin_conversation "
            "ON missions(origin_conversation_id, updated_at DESC)"
        )
        conn.commit()


def _required_text(value: str, label: str) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        raise MissionError(f"{label} must be non-empty")
    return text


ORIGIN_CHAT = "chat"
ORIGIN_PROJECT = "project"
_ORIGIN_KINDS = frozenset({ORIGIN_CHAT, ORIGIN_PROJECT})


def _row_origin(row: sqlite3.Row) -> dict[str, Any] | None:
    """Return the durable origin binding, or None for unbound legacy rows."""
    kind = row["origin_kind"] if "origin_kind" in row.keys() else None
    if not kind:
        return None
    return {
        "kind": kind,
        "conversation_id": row["origin_conversation_id"],
        "message_id": row["origin_message_id"],
        "project_id": row["origin_project_id"],
    }


def _row_to_mission(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "origin": _row_origin(row),
        "mission_id": row["mission_id"],
        "objective": row["objective"],
        "definition_of_done": json.loads(row["definition_of_done_json"]),
        "status": row["status"],
        "status_reason": row["status_reason"],
        "paused_from_status": row["paused_from_status"],
        "supervisor": {
            "id": row["supervisor_id"],
            "epoch": row["supervisor_epoch"],
        },
        "plan": {
            "ref": row["plan_ref"],
            "digest": row["plan_digest"],
            "review_state": row["plan_review_state"],
            "reviewer_id": row["plan_reviewer_id"],
            "review_evidence": json.loads(row["plan_review_evidence_json"])
            if row["plan_review_evidence_json"] else None,
            "payload": json.loads(row["plan_payload_json"])
            if row["plan_payload_json"] else None,
        },
        "builder_locator": json.loads(row["builder_locator_json"])
        if row["builder_locator_json"] else None,
        "checkpoint": json.loads(row["checkpoint_json"]),
        "source_cursors": json.loads(row["source_cursors_json"]),
        "last_cycle": json.loads(row["last_cycle_json"]) if row["last_cycle_json"] else None,
        "pending_escalation": json.loads(row["pending_escalation_json"])
        if row["pending_escalation_json"] else None,
        "candidate": {"ref": row["candidate_ref"], "digest": row["candidate_digest"]},
        "acceptance": {
            "state": row["acceptance_state"],
            "reviewer_id": row["acceptance_reviewer_id"],
            "evidence": json.loads(row["acceptance_evidence_json"])
            if row["acceptance_evidence_json"] else None,
        },
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_mission(mission_id: str, *, db_path: Path = MISSION_DB_FILE) -> dict[str, Any]:
    init_db(db_path=db_path)
    with kitty_db.connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM missions WHERE mission_id = ?", (mission_id,)
        ).fetchone()
    if row is None:
        raise MissionNotFound(f"no Mission with id {mission_id!r}")
    return _row_to_mission(row)


def resolve_chat_origin(
    *,
    conversation_id: str,
    message_id: str | None = None,
    db_path: Path = MISSION_DB_FILE,
) -> dict[str, Any]:
    """Resolve a Chat-originated binding server-side, project included.

    The project is decided here, at binding time, rather than read back later:
    prefer the project of the turn the request came from, then the
    conversation's own project. Moving the conversation to another project
    afterwards must not drag historical work with it, so the answer is stored
    on the Mission instead of being recomputed from live conversation state.

    A message id that does not belong to the named conversation is refused
    rather than silently dropped — a wrong anchor is worse than no anchor.
    """
    conversation_id = _required_text(conversation_id, "conversation_id")
    init_db(db_path=db_path)
    with kitty_db.connect(db_path) as conn:
        try:
            conversation = conn.execute(
                "SELECT project_id FROM chat_conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
        except sqlite3.OperationalError as exc:
            # A database that has never run a chat has no conversation tables.
            # That is "no such conversation", not an internal failure.
            raise MissionNotFound(
                f"no conversation with id {conversation_id!r}"
            ) from exc
        if conversation is None:
            raise MissionNotFound(f"no conversation with id {conversation_id!r}")

        project_id = conversation["project_id"]
        resolved_message_id: str | None = None
        if message_id:
            turn = conn.execute(
                "SELECT t.conversation_id AS conversation_id, t.project_id AS project_id "
                "FROM chat_messages m JOIN chat_turns t ON t.id = m.turn_id "
                "WHERE m.id = ?",
                (message_id,),
            ).fetchone()
            if turn is None:
                raise MissionNotFound(f"no chat message with id {message_id!r}")
            if turn["conversation_id"] != conversation_id:
                raise MissionError(
                    f"chat message {message_id!r} does not belong to conversation "
                    f"{conversation_id!r}"
                )
            resolved_message_id = message_id
            if turn["project_id"] is not None:
                project_id = turn["project_id"]

    return {
        "kind": ORIGIN_CHAT,
        "conversation_id": conversation_id,
        "message_id": resolved_message_id,
        "project_id": project_id,
    }


def project_origin(project_id: int) -> dict[str, Any]:
    """Bind a request raised from a Project directly, with no conversation."""
    if not isinstance(project_id, int) or isinstance(project_id, bool):
        raise MissionError("project_id must be an integer")
    return {
        "kind": ORIGIN_PROJECT,
        "conversation_id": None,
        "message_id": None,
        "project_id": project_id,
    }


def _validated_origin(origin: dict[str, Any] | None) -> dict[str, Any] | None:
    if origin is None:
        return None
    kind = origin.get("kind")
    if kind not in _ORIGIN_KINDS:
        raise MissionError(f"origin kind must be one of {sorted(_ORIGIN_KINDS)}, got {kind!r}")
    if kind == ORIGIN_CHAT and not origin.get("conversation_id"):
        raise MissionError("a chat origin must name its conversation")
    if kind == ORIGIN_PROJECT and origin.get("project_id") is None:
        raise MissionError("a project origin must name its project")
    return {
        "kind": kind,
        "conversation_id": origin.get("conversation_id"),
        "message_id": origin.get("message_id"),
        "project_id": origin.get("project_id"),
    }


def missions_for_conversation(
    conversation_id: str, *, db_path: Path = MISSION_DB_FILE
) -> list[dict[str, Any]]:
    """Return the Missions this conversation delegated, newest first.

    This is the server-owned recovery path: a browser with empty storage, or a
    different device entirely, can still find the work a chat started.
    """
    conversation_id = _required_text(conversation_id, "conversation_id")
    init_db(db_path=db_path)
    with kitty_db.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM missions WHERE origin_conversation_id = ? "
            "ORDER BY updated_at DESC, mission_id ASC",
            (conversation_id,),
        ).fetchall()
    return [_row_to_mission(row) for row in rows]


def missions_for_project(
    project_id: int, *, db_path: Path = MISSION_DB_FILE
) -> list[dict[str, Any]]:
    """Return every Mission bound to this project, newest first."""
    init_db(db_path=db_path)
    with kitty_db.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM missions WHERE origin_project_id = ? "
            "ORDER BY updated_at DESC, mission_id ASC",
            (project_id,),
        ).fetchall()
    return [_row_to_mission(row) for row in rows]


def mission_for_initiative(
    initiative_id: str, *, db_path: Path | None = None
) -> dict[str, Any] | None:
    """Return the Mission bound to this Builder initiative, if one is.

    Builder's initiative is not the Mission. Finishing the initiative is an
    implementation fact; whether the outcome was accepted is a separate
    decision recorded here. Callers that report completion need both, so they
    need this lookup — and they must treat ``None`` as "unknown", never as
    "accepted".
    """
    initiative_id = _required_text(initiative_id, "initiative_id")
    # Resolved at call time, not bound as a default: a default argument
    # captures MISSION_DB_FILE at import, so a runtime or test override of that
    # module attribute would be ignored and this would read the canonical
    # personal database instead of the one the caller selected.
    resolved = Path(db_path) if db_path is not None else MISSION_DB_FILE

    # Deliberately no init_db(), and deliberately not kitty_db.connect():
    # connect() creates the parent directory and the database file, so a
    # read-only result poll would bring a store into existence just by asking
    # about it. Opened read-only by URI; an absent or unreadable store is
    # reported as unavailable rather than conjured.
    if not resolved.is_file():
        raise MissionError(f"Mission store is unavailable: {resolved} does not exist")
    conn = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM missions WHERE builder_locator_json IS NOT NULL "
            "ORDER BY updated_at DESC, mission_id ASC"
        ).fetchall()
    except sqlite3.Error as exc:
        raise MissionError(f"Mission store is unavailable: {exc}") from exc
    finally:
        conn.close()
    for row in rows:
        locator = json.loads(row["builder_locator_json"])
        if isinstance(locator, dict) and locator.get("initiative_id") == initiative_id:
            return _row_to_mission(row)
    return None


def list_missions(*, db_path: Path = MISSION_DB_FILE) -> list[dict[str, Any]]:
    """Return durable Mission rows with the most recently updated first."""
    init_db(db_path=db_path)
    with kitty_db.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM missions ORDER BY updated_at DESC, mission_id ASC"
        ).fetchall()
    return [_row_to_mission(row) for row in rows]


def create_mission(
    *,
    mission_id: str,
    objective: str,
    definition_of_done: list[str],
    supervisor_id: str,
    origin: dict[str, Any] | None = None,
    db_path: Path = MISSION_DB_FILE,
) -> dict[str, Any]:
    mission_id = _required_text(mission_id, "mission_id")
    objective = _required_text(objective, "objective")
    supervisor_id = _required_text(supervisor_id, "supervisor_id")
    if not definition_of_done or any(
        not isinstance(item, str) or not item.strip() for item in definition_of_done
    ):
        raise MissionError("definition_of_done must contain non-empty strings")
    bound = _validated_origin(origin)
    now = time.time()
    init_db(db_path=db_path)
    try:
        with kitty_db.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO missions "
                "(mission_id, objective, definition_of_done_json, status, "
                "supervisor_id, supervisor_epoch, created_at, updated_at, "
                "origin_kind, origin_conversation_id, origin_message_id, origin_project_id) "
                "VALUES (?, ?, ?, 'PLANNING', ?, 1, ?, ?, ?, ?, ?, ?)",
                (
                    mission_id,
                    objective,
                    json.dumps(definition_of_done),
                    supervisor_id,
                    now,
                    now,
                    bound["kind"] if bound else None,
                    bound["conversation_id"] if bound else None,
                    bound["message_id"] if bound else None,
                    bound["project_id"] if bound else None,
                ),
            )
            conn.execute(
                "INSERT INTO mission_events "
                "(mission_id,event_type,supervisor_epoch,payload_json,created_at) "
                "VALUES (?, 'mission_created', 1, ?, ?)",
                (mission_id, json.dumps({"objective": objective}), now),
            )
            conn.commit()
    except sqlite3.IntegrityError as exc:
        raise MissionError(f"Mission {mission_id!r} already exists") from exc
    return get_mission(mission_id, db_path=db_path)


def ensure_mission(
    *,
    mission_id: str,
    objective: str,
    definition_of_done: list[str],
    supervisor_id: str,
    origin: dict[str, Any] | None = None,
    db_path: Path = MISSION_DB_FILE,
) -> dict[str, Any]:
    """Create one Mission identity or return the exact existing outcome.

    This is the idempotent creation seam for request retries. A caller may
    replay the same stable Mission id without creating another record, but the
    id can never be silently reused for a different objective/definition of
    done. Existing supervisor/lifecycle state is never reset on replay.

    Origin is bound once, at creation. A replay carrying the same origin is
    accepted; one carrying a different origin is refused rather than silently
    rehoming finished work. A replay that omits origin leaves the stored
    binding alone, so a retry from a client that has lost its context cannot
    erase where the work came from.
    """
    mission_id = _required_text(mission_id, "mission_id")
    objective = _required_text(objective, "objective")
    supervisor_id = _required_text(supervisor_id, "supervisor_id")
    if not definition_of_done or any(
        not isinstance(item, str) or not item.strip() for item in definition_of_done
    ):
        raise MissionError("definition_of_done must contain non-empty strings")
    bound = _validated_origin(origin)

    init_db(db_path=db_path)
    now = time.time()
    with kitty_db.connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM missions WHERE mission_id=?", (mission_id,)
        ).fetchone()
        if row is not None:
            current = _row_to_mission(row)
            if (
                current["objective"] != objective
                or current["definition_of_done"] != definition_of_done
            ):
                raise MissionError(
                    f"Mission {mission_id!r} already exists for a different outcome"
                )
            if bound is not None and current["origin"] not in (None, bound):
                raise MissionError(
                    f"Mission {mission_id!r} is already bound to a different origin"
                )
            conn.rollback()
            return current

        conn.execute(
            "INSERT INTO missions "
            "(mission_id, objective, definition_of_done_json, status, "
            "supervisor_id, supervisor_epoch, created_at, updated_at, "
            "origin_kind, origin_conversation_id, origin_message_id, origin_project_id) "
            "VALUES (?, ?, ?, 'PLANNING', ?, 1, ?, ?, ?, ?, ?, ?)",
            (
                mission_id,
                objective,
                json.dumps(definition_of_done),
                supervisor_id,
                now,
                now,
                bound["kind"] if bound else None,
                bound["conversation_id"] if bound else None,
                bound["message_id"] if bound else None,
                bound["project_id"] if bound else None,
            ),
        )
        conn.execute(
            "INSERT INTO mission_events "
            "(mission_id,event_type,supervisor_epoch,payload_json,created_at) "
            "VALUES (?, 'mission_created', 1, ?, ?)",
            (mission_id, json.dumps({"objective": objective}), now),
        )
        conn.commit()
    return get_mission(mission_id, db_path=db_path)


def _append_event(
    conn: sqlite3.Connection,
    *,
    mission_id: str,
    event_type: str,
    supervisor_epoch: int | None,
    payload: dict[str, Any],
    now: float,
) -> None:
    conn.execute(
        "INSERT INTO mission_events "
        "(mission_id,event_type,supervisor_epoch,payload_json,created_at) VALUES (?,?,?,?,?)",
        (mission_id, event_type, supervisor_epoch, json.dumps(payload, sort_keys=True), now),
    )


def bind_builder_locator(
    mission_id: str,
    *,
    initiative_id: str,
    task_id: str | None = None,
    db_path: Path = MISSION_DB_FILE,
) -> dict[str, Any]:
    """Bind one Gateway Mission to Builder identifiers without copying Builder state.

    The Builder initiative is immutable once bound. A later approval may add the
    durable Builder task id exactly once. Replays preserve the existing locator
    so an ambiguous/lost HTTP receipt cannot retarget or regress the Mission.
    """
    mission_id = _required_text(mission_id, "mission_id")
    initiative_id = _required_text(initiative_id, "initiative_id")
    if task_id is not None:
        task_id = _required_text(task_id, "task_id")
    init_db(db_path=db_path)
    now = time.time()
    with kitty_db.connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT builder_locator_json, supervisor_epoch FROM missions WHERE mission_id=?",
            (mission_id,),
        ).fetchone()
        if row is None:
            raise MissionNotFound(f"no Mission with id {mission_id!r}")

        current = json.loads(row["builder_locator_json"]) if row["builder_locator_json"] else None
        if current is not None and current.get("initiative_id") != initiative_id:
            raise MissionError("Mission is already bound to a different Builder initiative")

        current_task = current.get("task_id") if current else None
        if current_task is not None and task_id is not None and current_task != task_id:
            raise MissionError("Mission is already bound to a different Builder task")

        resolved = {
            "initiative_id": initiative_id,
            "task_id": current_task if current_task is not None else task_id,
        }
        if current == resolved:
            conn.rollback()
            return get_mission(mission_id, db_path=db_path)

        conn.execute(
            "UPDATE missions SET builder_locator_json=?, updated_at=? WHERE mission_id=?",
            (json.dumps(resolved, sort_keys=True), now, mission_id),
        )
        _append_event(
            conn,
            mission_id=mission_id,
            event_type="builder_locator_bound",
            supervisor_epoch=int(row["supervisor_epoch"]),
            payload=resolved,
            now=now,
        )
        conn.commit()
    return get_mission(mission_id, db_path=db_path)


def set_plan(
    mission_id: str, *, plan_ref: str, plan_digest: str,
    plan_payload: dict[str, Any] | None = None, db_path: Path = MISSION_DB_FILE,
) -> dict[str, Any]:
    plan_ref = _required_text(plan_ref, "plan_ref")
    plan_digest = _required_text(plan_digest, "plan_digest")
    mission_id = _required_text(mission_id, "mission_id")
    payload_json: str | None = None
    if plan_payload is not None:
        if not isinstance(plan_payload, dict):
            raise MissionError("plan_payload must be a JSON object")
        if bi.manifest_sha256(plan_payload) != plan_digest:
            raise MissionError("plan payload digest does not match plan_digest")
        payload_json = json.dumps(plan_payload, sort_keys=True)
    init_db(db_path=db_path)
    now = time.time()
    with kitty_db.connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT plan_ref, plan_digest, plan_payload_json, plan_review_state, status, "
            "supervisor_epoch FROM missions WHERE mission_id=?",
            (mission_id,),
        ).fetchone()
        if row is None:
            raise MissionNotFound(f"no Mission with id {mission_id!r}")
        same_plan = row["plan_ref"] == plan_ref and row["plan_digest"] == plan_digest
        if same_plan and (payload_json is None or row["plan_payload_json"] == payload_json):
            conn.rollback()
            return get_mission(mission_id, db_path=db_path)
        if row["status"] == "STOPPED":
            raise MissionError("stopped Mission cannot receive a new plan")
        if row["status"] == "DONE":
            raise MissionError("completed Mission cannot receive a new plan")
        # Backfilling the exact manifest onto a previously digest-only plan must
        # reopen review: the earlier reviewer could not have inspected this payload.
        conn.execute(
            "UPDATE missions SET plan_ref=?, plan_digest=?, plan_payload_json=?, "
            "plan_review_state='unreviewed', plan_reviewer_id=NULL, "
            "plan_review_evidence_json=NULL, status='PLAN_REVIEW', updated_at=? "
            "WHERE mission_id=?",
            (plan_ref, plan_digest, payload_json, now, mission_id),
        )
        _append_event(
            conn, mission_id=mission_id, event_type="plan_set",
            supervisor_epoch=int(row["supervisor_epoch"]),
            payload={"plan_ref": plan_ref, "plan_digest": plan_digest}, now=now,
        )
        conn.commit()
    return get_mission(mission_id, db_path=db_path)


def record_plan_review(
    mission_id: str, *, reviewer_id: str, plan_digest: str, verdict: str,
    evidence: dict[str, Any] | None = None, db_path: Path = MISSION_DB_FILE,
) -> dict[str, Any]:
    reviewer_id = _required_text(reviewer_id, "reviewer_id")
    mission = get_mission(mission_id, db_path=db_path)
    if reviewer_id == mission["supervisor"]["id"]:
        raise MissionError("plan review must be independent of the accountable supervisor")
    if plan_digest != mission["plan"]["digest"]:
        raise MissionError("review digest does not match the current plan")
    if verdict not in {"approved", "rejected"}:
        raise MissionError("plan review verdict must be approved or rejected")
    now = time.time()
    status = "PLAN_REVIEW" if verdict == "approved" else "PLANNING"
    with kitty_db.connect(db_path) as conn:
        cursor = conn.execute(
            "UPDATE missions SET plan_review_state=?, plan_reviewer_id=?, "
            "plan_review_evidence_json=?, status=?, updated_at=? "
            "WHERE mission_id=? AND plan_digest=? AND status='PLAN_REVIEW' "
            "AND supervisor_id<>?",
            (
                verdict, reviewer_id, json.dumps(evidence or {}, sort_keys=True),
                status, now, mission_id, plan_digest, reviewer_id,
            ),
        )
        if cursor.rowcount != 1:
            raise MissionError(
                "plan review no longer matches the current plan or independent supervisor"
            )
        epoch_row = conn.execute(
            "SELECT supervisor_epoch FROM missions WHERE mission_id=?", (mission_id,)
        ).fetchone()
        _append_event(
            conn, mission_id=mission_id, event_type="plan_reviewed",
            supervisor_epoch=int(epoch_row[0]),
            payload={"plan_digest": plan_digest, "reviewer_id": reviewer_id, "verdict": verdict}, now=now,
        )
        conn.commit()
    return get_mission(mission_id, db_path=db_path)


def begin_execution(mission_id: str, *, db_path: Path = MISSION_DB_FILE) -> dict[str, Any]:
    mission = get_mission(mission_id, db_path=db_path)
    if mission["status"] != "PLAN_REVIEW":
        raise MissionError("Mission can begin execution only from PLAN_REVIEW state")
    if mission["plan"]["review_state"] != "approved" or not mission["plan"]["digest"]:
        raise MissionError("Mission cannot execute without an approved plan review")
    if mission["plan"]["reviewer_id"] == mission["supervisor"]["id"]:
        raise MissionError("Mission cannot execute without an independent current plan review")
    now = time.time()
    with kitty_db.connect(db_path) as conn:
        cursor = conn.execute(
            "UPDATE missions SET status='EXECUTING', updated_at=? "
            "WHERE mission_id=? AND status='PLAN_REVIEW' AND plan_digest=? "
            "AND plan_review_state='approved' AND plan_reviewer_id<>supervisor_id "
            "AND supervisor_id=? AND supervisor_epoch=?",
            (
                now, mission_id, mission["plan"]["digest"],
                mission["supervisor"]["id"], mission["supervisor"]["epoch"],
            ),
        )
        if cursor.rowcount != 1:
            raise MissionError("Mission plan approval changed before execution")
        _append_event(
            conn, mission_id=mission_id, event_type="execution_started",
            supervisor_epoch=mission["supervisor"]["epoch"],
            payload={"plan_digest": mission["plan"]["digest"]}, now=now,
        )
        conn.commit()
    return get_mission(mission_id, db_path=db_path)


def replace_supervisor(
    mission_id: str, *, new_supervisor_id: str, expected_supervisor_id: str,
    expected_epoch: int, db_path: Path = MISSION_DB_FILE,
) -> dict[str, Any]:
    new_supervisor_id = _required_text(new_supervisor_id, "new_supervisor_id")
    init_db(db_path=db_path)
    now = time.time()
    with kitty_db.connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT status, supervisor_id, supervisor_epoch, plan_review_state, "
            "plan_reviewer_id FROM missions WHERE mission_id=?",
            (mission_id,),
        ).fetchone()
        if row is None:
            raise MissionNotFound(f"no Mission with id {mission_id!r}")
        if (
            row["supervisor_id"] != expected_supervisor_id
            or row["supervisor_epoch"] != expected_epoch
        ):
            raise MissionError("stale supervisor identity or epoch")
        if (
            row["status"] == "EXECUTING"
            and row["plan_review_state"] == "approved"
            and row["plan_reviewer_id"] == new_supervisor_id
        ):
            raise MissionError(
                "executing Mission supervisor must remain independent of its plan reviewer"
            )
        cursor = conn.execute(
            "UPDATE missions SET supervisor_id=?, supervisor_epoch=supervisor_epoch+1, updated_at=? "
            "WHERE mission_id=? AND supervisor_id=? AND supervisor_epoch=?",
            (new_supervisor_id, now, mission_id, expected_supervisor_id, expected_epoch),
        )
        if cursor.rowcount != 1:
            raise MissionError("stale supervisor identity or epoch")
        _append_event(
            conn, mission_id=mission_id, event_type="supervisor_replaced",
            supervisor_epoch=expected_epoch + 1,
            payload={"from": expected_supervisor_id, "to": new_supervisor_id}, now=now,
        )
        conn.commit()
    return get_mission(mission_id, db_path=db_path)


def update_checkpoint(
    mission_id: str, *, supervisor_id: str, supervisor_epoch: int,
    checkpoint: dict[str, Any], db_path: Path = MISSION_DB_FILE,
) -> dict[str, Any]:
    if not isinstance(checkpoint, dict):
        raise MissionError("checkpoint must be an object")
    mission = get_mission(mission_id, db_path=db_path)
    if mission["status"] == "STOPPED":
        raise MissionError("stopped Mission rejects checkpoint mutation")
    if mission["status"] == "DONE":
        raise MissionError("completed Mission rejects checkpoint mutation")
    init_db(db_path=db_path)
    now = time.time()
    encoded = json.dumps(checkpoint, sort_keys=True)
    with kitty_db.connect(db_path) as conn:
        cursor = conn.execute(
            "UPDATE missions SET checkpoint_json=?, updated_at=? "
            "WHERE mission_id=? AND supervisor_id=? AND supervisor_epoch=? "
            "AND status NOT IN ('STOPPED','DONE')",
            (encoded, now, mission_id, supervisor_id, supervisor_epoch),
        )
        if cursor.rowcount != 1:
            current = get_mission(mission_id, db_path=db_path)
            if current["status"] == "STOPPED":
                raise MissionError("stopped Mission rejects checkpoint mutation")
            if current["status"] == "DONE":
                raise MissionError("completed Mission rejects checkpoint mutation")
            raise MissionError("stale supervisor identity or epoch")
        _append_event(
            conn, mission_id=mission_id, event_type="checkpoint_updated",
            supervisor_epoch=supervisor_epoch,
            payload={"checkpoint": checkpoint}, now=now,
        )
        conn.commit()
    return get_mission(mission_id, db_path=db_path)


def assert_supervisor(
    mission_id: str, *, supervisor_id: str, supervisor_epoch: int,
    db_path: Path = MISSION_DB_FILE,
) -> dict[str, Any]:
    mission = get_mission(mission_id, db_path=db_path)
    if mission["supervisor"] != {"id": supervisor_id, "epoch": supervisor_epoch}:
        raise MissionError("stale supervisor identity or epoch")
    return mission


def record_cycle(
    mission_id: str, *, supervisor_id: str, supervisor_epoch: int,
    source_cursors: dict[str, str], cycle: dict[str, Any],
    pending_escalation: dict[str, Any] | None = None,
    expected_last_cycle: dict[str, Any] | None | object = _UNSET,
    db_path: Path = MISSION_DB_FILE,
) -> dict[str, Any]:
    if not isinstance(source_cursors, dict) or not isinstance(cycle, dict):
        raise MissionError("cycle state must be structured objects")
    mission = get_mission(mission_id, db_path=db_path)
    if mission["status"] != "EXECUTING":
        raise MissionError(f"Mission cycle requires EXECUTING state, got {mission['status']}")
    now = time.time()
    where = (
        "WHERE mission_id=? AND supervisor_id=? AND supervisor_epoch=? "
        "AND status='EXECUTING'"
    )
    params: list[Any] = [
        json.dumps(source_cursors, sort_keys=True),
        json.dumps(cycle, sort_keys=True),
        json.dumps(pending_escalation, sort_keys=True) if pending_escalation else None,
        now, mission_id, supervisor_id, supervisor_epoch,
    ]
    if expected_last_cycle is not _UNSET:
        if expected_last_cycle is None:
            where += " AND last_cycle_json IS NULL"
        else:
            where += " AND last_cycle_json=?"
            params.append(json.dumps(expected_last_cycle, sort_keys=True))
    with kitty_db.connect(db_path) as conn:
        cursor = conn.execute(
            "UPDATE missions SET source_cursors_json=?, last_cycle_json=?, "
            "pending_escalation_json=?, updated_at=? " + where,
            tuple(params),
        )
        if cursor.rowcount != 1:
            if expected_last_cycle is not _UNSET:
                raise MissionError(
                    "Mission cycle state or delegation state changed before update"
                )
            raise MissionError("stale supervisor identity or epoch")
        _append_event(
            conn, mission_id=mission_id, event_type="supervisor_cycle",
            supervisor_epoch=supervisor_epoch, payload=cycle, now=now,
        )
        conn.commit()
    return get_mission(mission_id, db_path=db_path)


def record_notification_delivery(
    mission_id: str, *, escalation_key: str,
    expected_pending_escalation: dict[str, Any],
    expected_last_cycle: dict[str, Any], delivered_cycle: dict[str, Any],
    db_path: Path = MISSION_DB_FILE,
) -> dict[str, Any]:
    """Persist a completed notification without reviving stale Mission state."""
    escalation_key = _required_text(escalation_key, "escalation_key")
    if expected_pending_escalation.get("key") != escalation_key:
        raise MissionError("notification key does not match pending escalation")
    if expected_pending_escalation.get("notification_state") != "pending":
        raise MissionError("notification delivery requires a pending receipt")
    if not isinstance(expected_last_cycle, dict) or not isinstance(delivered_cycle, dict):
        raise MissionError("notification delivery cycles must be objects")

    expected_pending_json = json.dumps(expected_pending_escalation, sort_keys=True)
    delivered_pending = dict(expected_pending_escalation)
    delivered_pending["notification_state"] = "delivered"
    delivered_pending_json = json.dumps(delivered_pending, sort_keys=True)
    expected_cycle_json = json.dumps(expected_last_cycle, sort_keys=True)
    delivered_cycle_json = json.dumps(delivered_cycle, sort_keys=True)
    now = time.time()
    init_db(db_path=db_path)
    with kitty_db.connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT pending_escalation_json, last_cycle_json, supervisor_epoch "
            "FROM missions WHERE mission_id=?",
            (mission_id,),
        ).fetchone()
        if row is None:
            raise MissionNotFound(f"no Mission with id {mission_id!r}")
        if row["pending_escalation_json"] != expected_pending_json:
            raise MissionError("notification state changed before delivery receipt update")
        if row["last_cycle_json"] == expected_cycle_json:
            cursor = conn.execute(
                "UPDATE missions SET pending_escalation_json=?, last_cycle_json=?, updated_at=? "
                "WHERE mission_id=? AND pending_escalation_json=? AND last_cycle_json=?",
                (
                    delivered_pending_json, delivered_cycle_json, now, mission_id,
                    expected_pending_json, expected_cycle_json,
                ),
            )
        else:
            cursor = conn.execute(
                "UPDATE missions SET pending_escalation_json=?, updated_at=? "
                "WHERE mission_id=? AND pending_escalation_json=?",
                (delivered_pending_json, now, mission_id, expected_pending_json),
            )
        if cursor.rowcount != 1:
            raise MissionError("notification state changed before delivery receipt update")
        _append_event(
            conn, mission_id=mission_id, event_type="notification_delivered",
            supervisor_epoch=int(row["supervisor_epoch"]),
            payload={"escalation_key": escalation_key}, now=now,
        )
        conn.commit()
    return get_mission(mission_id, db_path=db_path)


def record_candidate(
    mission_id: str, *, candidate_ref: str, candidate_digest: str,
    db_path: Path = MISSION_DB_FILE,
) -> dict[str, Any]:
    candidate_ref = _required_text(candidate_ref, "candidate_ref")
    candidate_digest = _required_text(candidate_digest, "candidate_digest")
    mission = get_mission(mission_id, db_path=db_path)
    if mission["status"] == "STOPPED":
        raise MissionError("stopped Mission cannot receive a candidate")
    if mission["status"] == "DONE":
        raise MissionError("completed Mission cannot receive a candidate")
    now = time.time()
    with kitty_db.connect(db_path) as conn:
        cursor = conn.execute(
            "UPDATE missions SET candidate_ref=?, candidate_digest=?, "
            "acceptance_state='unreviewed', acceptance_reviewer_id=NULL, "
            "acceptance_evidence_json=NULL, status='VERIFYING', updated_at=? "
            "WHERE mission_id=? AND status NOT IN ('STOPPED','DONE')",
            (candidate_ref, candidate_digest, now, mission_id),
        )
        if cursor.rowcount != 1:
            raise MissionError("Mission became stopped or completed before candidate update")
        _append_event(
            conn, mission_id=mission_id, event_type="candidate_recorded",
            supervisor_epoch=mission["supervisor"]["epoch"],
            payload={"candidate_ref": candidate_ref, "candidate_digest": candidate_digest},
            now=now,
        )
        conn.commit()
    return get_mission(mission_id, db_path=db_path)


def record_acceptance(
    mission_id: str, *, reviewer_id: str, candidate_digest: str, verdict: str,
    evidence: dict[str, Any] | None = None, db_path: Path = MISSION_DB_FILE,
) -> dict[str, Any]:
    reviewer_id = _required_text(reviewer_id, "reviewer_id")
    mission = get_mission(mission_id, db_path=db_path)
    if reviewer_id == mission["supervisor"]["id"]:
        raise MissionError("acceptance review must be independent of the accountable supervisor")
    if candidate_digest != mission["candidate"]["digest"]:
        raise MissionError("acceptance digest does not match the current candidate")
    if verdict not in {"accepted", "rejected"}:
        raise MissionError("acceptance verdict must be accepted or rejected")
    now = time.time()
    status = "DONE" if verdict == "accepted" else "REPAIRING"
    with kitty_db.connect(db_path) as conn:
        cursor = conn.execute(
            "UPDATE missions SET acceptance_state=?, acceptance_reviewer_id=?, "
            "acceptance_evidence_json=?, status=?, updated_at=? "
            "WHERE mission_id=? AND candidate_digest=? AND status='VERIFYING' "
            "AND supervisor_id<>?",
            (
                verdict, reviewer_id, json.dumps(evidence or {}, sort_keys=True),
                status, now, mission_id, candidate_digest, reviewer_id,
            ),
        )
        if cursor.rowcount != 1:
            raise MissionError(
                "acceptance no longer matches the current candidate or independent supervisor"
            )
        epoch_row = conn.execute(
            "SELECT supervisor_epoch FROM missions WHERE mission_id=?", (mission_id,)
        ).fetchone()
        _append_event(
            conn, mission_id=mission_id, event_type="acceptance_reviewed",
            supervisor_epoch=int(epoch_row[0]),
            payload={"candidate_digest": candidate_digest, "reviewer_id": reviewer_id, "verdict": verdict},
            now=now,
        )
        conn.commit()
    return get_mission(mission_id, db_path=db_path)


def _set_status(
    mission_id: str, *, status: str, reason: str | None,
    event_type: str, db_path: Path,
) -> dict[str, Any]:
    mission = get_mission(mission_id, db_path=db_path)
    now = time.time()
    with kitty_db.connect(db_path) as conn:
        conn.execute(
            "UPDATE missions SET status=?, status_reason=?, updated_at=? WHERE mission_id=?",
            (status, reason, now, mission_id),
        )
        _append_event(
            conn, mission_id=mission_id, event_type=event_type,
            supervisor_epoch=mission["supervisor"]["epoch"],
            payload={"status": status, "reason": reason}, now=now,
        )
        conn.commit()
    return get_mission(mission_id, db_path=db_path)


def pause_mission(
    mission_id: str, *, reason: str, db_path: Path = MISSION_DB_FILE
) -> dict[str, Any]:
    reason = _required_text(reason, "reason")
    mission = get_mission(mission_id, db_path=db_path)
    if mission["status"] == "STOPPED":
        raise MissionError("stopped Mission cannot be paused")
    if mission["status"] == "DONE":
        raise MissionError("completed Mission cannot be paused")
    if mission["status"] == "PAUSED":
        raise MissionError("Mission is already paused")
    paused_from = mission["status"]
    now = time.time()
    with kitty_db.connect(db_path) as conn:
        cursor = conn.execute(
            "UPDATE missions SET status='PAUSED', status_reason=?, paused_from_status=?, updated_at=? "
            "WHERE mission_id=? AND status=?",
            (reason, paused_from, now, mission_id, paused_from),
        )
        if cursor.rowcount != 1:
            raise MissionError("Mission state changed before pause")
        epoch_row = conn.execute(
            "SELECT supervisor_epoch FROM missions WHERE mission_id=?", (mission_id,)
        ).fetchone()
        _append_event(
            conn, mission_id=mission_id, event_type="mission_paused",
            supervisor_epoch=int(epoch_row[0]),
            payload={"status": "PAUSED", "paused_from": paused_from, "reason": reason},
            now=now,
        )
        conn.commit()
    return get_mission(mission_id, db_path=db_path)


def resume_mission(
    mission_id: str, *, db_path: Path = MISSION_DB_FILE
) -> dict[str, Any]:
    mission = get_mission(mission_id, db_path=db_path)
    if mission["status"] == "STOPPED":
        raise MissionError("stopped Mission cannot be resumed")
    if mission["status"] != "PAUSED":
        raise MissionError(f"Mission is not paused: {mission['status']}")
    target = mission.get("paused_from_status")
    if target not in {
        "PLANNING", "PLAN_REVIEW", "EXECUTING", "VERIFYING", "REPAIRING",
        "BLOCKED", "PARTIALLY_COMPLETE", "FAILED",
    }:
        raise MissionError("Mission pause origin is unavailable; cannot resume safely")

    where = "WHERE mission_id=? AND status='PAUSED' AND paused_from_status=?"
    params: list[Any] = [mission_id, target]
    if target == "EXECUTING":
        if mission["plan"]["review_state"] != "approved" or not mission["plan"]["digest"]:
            raise MissionError("Mission cannot resume execution without an approved plan review")
        if mission["plan"]["reviewer_id"] == mission["supervisor"]["id"]:
            raise MissionError("Mission cannot resume without an independent current plan review")
        where += (
            " AND plan_review_state='approved' AND plan_reviewer_id<>supervisor_id "
            "AND plan_digest=?"
        )
        params.append(mission["plan"]["digest"])
    elif target == "VERIFYING":
        if not mission["candidate"]["digest"] or mission["acceptance"]["state"] != "unreviewed":
            raise MissionError("Mission cannot resume verification without its unreviewed candidate")
        where += " AND candidate_digest=? AND acceptance_state='unreviewed'"
        params.append(mission["candidate"]["digest"])

    now = time.time()
    with kitty_db.connect(db_path) as conn:
        cursor = conn.execute(
            "UPDATE missions SET status=?, status_reason=NULL, paused_from_status=NULL, updated_at=? "
            + where,
            (target, now, *params),
        )
        if cursor.rowcount != 1:
            raise MissionError("Mission state or resume prerequisite changed before resume")
        epoch_row = conn.execute(
            "SELECT supervisor_epoch FROM missions WHERE mission_id=?", (mission_id,)
        ).fetchone()
        _append_event(
            conn, mission_id=mission_id, event_type="mission_resumed",
            supervisor_epoch=int(epoch_row[0]), payload={"status": target, "reason": None},
            now=now,
        )
        conn.commit()
    return get_mission(mission_id, db_path=db_path)


def stop_mission(
    mission_id: str, *, reason: str, db_path: Path = MISSION_DB_FILE
) -> dict[str, Any]:
    return _set_status(
        mission_id, status="STOPPED", reason=_required_text(reason, "reason"),
        event_type="mission_stopped", db_path=db_path,
    )


def record_worker_report(
    mission_id: str, *, supervisor_id: str, supervisor_epoch: int,
    worker_id: str, report: dict[str, Any], evidence_locator: str,
    db_path: Path = MISSION_DB_FILE,
) -> dict[str, Any]:
    """Preserve a worker claim as report evidence, never as verified state."""
    worker_id = _required_text(worker_id, "worker_id")
    evidence_locator = _required_text(evidence_locator, "evidence_locator")
    if not isinstance(report, dict):
        raise MissionError("worker report must be an object")
    init_db(db_path=db_path)
    now = time.time()
    entry = {
        "worker_id": worker_id,
        "report": report,
        "evidence_locator": evidence_locator,
    }
    with kitty_db.connect(db_path) as conn:
        # Serialize the read/append/write sequence across processes. A plain
        # read followed by update_checkpoint() can silently lose a concurrent
        # report because both writers replace the same JSON checkpoint.
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT status, supervisor_id, supervisor_epoch, checkpoint_json "
            "FROM missions WHERE mission_id=?",
            (mission_id,),
        ).fetchone()
        if row is None:
            raise MissionNotFound(f"no Mission with id {mission_id!r}")
        if row["supervisor_id"] != supervisor_id or row["supervisor_epoch"] != supervisor_epoch:
            raise MissionError("stale supervisor identity or epoch")
        if row["status"] == "STOPPED":
            raise MissionError("stopped Mission rejects checkpoint mutation")
        if row["status"] == "DONE":
            raise MissionError("completed Mission rejects checkpoint mutation")

        checkpoint = json.loads(row["checkpoint_json"])
        worker_reports = list(checkpoint.get("worker_reports") or [])
        worker_reports.append(entry)
        checkpoint["worker_reports"] = worker_reports
        encoded = json.dumps(checkpoint, sort_keys=True)
        cursor = conn.execute(
            "UPDATE missions SET checkpoint_json=?, updated_at=? "
            "WHERE mission_id=? AND supervisor_id=? AND supervisor_epoch=? "
            "AND status NOT IN ('STOPPED','DONE')",
            (encoded, now, mission_id, supervisor_id, supervisor_epoch),
        )
        if cursor.rowcount != 1:
            raise MissionError("Mission state changed before worker report update")
        _append_event(
            conn, mission_id=mission_id, event_type="checkpoint_updated",
            supervisor_epoch=supervisor_epoch, payload={"checkpoint": checkpoint}, now=now,
        )
        _append_event(
            conn, mission_id=mission_id, event_type="worker_report_received",
            supervisor_epoch=supervisor_epoch, payload=entry, now=now,
        )
        conn.commit()
    return get_mission(mission_id, db_path=db_path)
