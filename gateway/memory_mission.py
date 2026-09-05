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

from gateway import db as kitty_db
from gateway.paths import KITTY_DB_FILE

MISSION_DB_FILE = KITTY_DB_FILE


class MissionError(RuntimeError):
    """Base Mission state error."""


class MissionNotFound(MissionError):
    """Raised when a Mission id has no durable row."""


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
                supervisor_id TEXT NOT NULL,
                supervisor_epoch INTEGER NOT NULL,
                plan_ref TEXT,
                plan_digest TEXT,
                plan_review_state TEXT NOT NULL DEFAULT 'unreviewed',
                plan_reviewer_id TEXT,
                plan_review_evidence_json TEXT,
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


def _required_text(value: str, label: str) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        raise MissionError(f"{label} must be non-empty")
    return text


def _row_to_mission(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "mission_id": row["mission_id"],
        "objective": row["objective"],
        "definition_of_done": json.loads(row["definition_of_done_json"]),
        "status": row["status"],
        "status_reason": row["status_reason"],
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
        },
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


def create_mission(
    *,
    mission_id: str,
    objective: str,
    definition_of_done: list[str],
    supervisor_id: str,
    db_path: Path = MISSION_DB_FILE,
) -> dict[str, Any]:
    mission_id = _required_text(mission_id, "mission_id")
    objective = _required_text(objective, "objective")
    supervisor_id = _required_text(supervisor_id, "supervisor_id")
    if not definition_of_done or any(
        not isinstance(item, str) or not item.strip() for item in definition_of_done
    ):
        raise MissionError("definition_of_done must contain non-empty strings")
    now = time.time()
    init_db(db_path=db_path)
    try:
        with kitty_db.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO missions "
                "(mission_id, objective, definition_of_done_json, status, "
                "supervisor_id, supervisor_epoch, created_at, updated_at) "
                "VALUES (?, ?, ?, 'PLANNING', ?, 1, ?, ?)",
                (mission_id, objective, json.dumps(definition_of_done), supervisor_id, now, now),
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


def set_plan(
    mission_id: str, *, plan_ref: str, plan_digest: str, db_path: Path = MISSION_DB_FILE
) -> dict[str, Any]:
    plan_ref = _required_text(plan_ref, "plan_ref")
    plan_digest = _required_text(plan_digest, "plan_digest")
    mission = get_mission(mission_id, db_path=db_path)
    if mission["status"] == "STOPPED":
        raise MissionError("stopped Mission cannot receive a new plan")
    if mission["status"] == "DONE":
        raise MissionError("completed Mission cannot receive a new plan")
    now = time.time()
    with kitty_db.connect(db_path) as conn:
        cursor = conn.execute(
            "UPDATE missions SET plan_ref=?, plan_digest=?, plan_review_state='unreviewed', "
            "plan_reviewer_id=NULL, plan_review_evidence_json=NULL, status='PLAN_REVIEW', updated_at=? "
            "WHERE mission_id=? AND status NOT IN ('STOPPED','DONE')",
            (plan_ref, plan_digest, now, mission_id),
        )
        if cursor.rowcount != 1:
            raise MissionError("Mission became stopped or completed before plan update")
        _append_event(
            conn, mission_id=mission_id, event_type="plan_set",
            supervisor_epoch=mission["supervisor"]["epoch"],
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
    expected_last_cycle: dict[str, Any] | None = None,
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
    if expected_last_cycle is not None:
        where += " AND last_cycle_json=?"
        params.append(json.dumps(expected_last_cycle, sort_keys=True))
    with kitty_db.connect(db_path) as conn:
        cursor = conn.execute(
            "UPDATE missions SET source_cursors_json=?, last_cycle_json=?, "
            "pending_escalation_json=?, updated_at=? " + where,
            tuple(params),
        )
        if cursor.rowcount != 1:
            if expected_last_cycle is not None:
                raise MissionError("delegation state changed before Mission cycle update")
            raise MissionError("stale supervisor identity or epoch")
        _append_event(
            conn, mission_id=mission_id, event_type="supervisor_cycle",
            supervisor_epoch=supervisor_epoch, payload=cycle, now=now,
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
    now = time.time()
    with kitty_db.connect(db_path) as conn:
        cursor = conn.execute(
            "UPDATE missions SET status='PAUSED', status_reason=?, updated_at=? "
            "WHERE mission_id=? AND status NOT IN ('STOPPED','DONE')",
            (reason, now, mission_id),
        )
        if cursor.rowcount != 1:
            raise MissionError("Mission became stopped or completed before pause")
        epoch_row = conn.execute(
            "SELECT supervisor_epoch FROM missions WHERE mission_id=?", (mission_id,)
        ).fetchone()
        _append_event(
            conn, mission_id=mission_id, event_type="mission_paused",
            supervisor_epoch=int(epoch_row[0]), payload={"status": "PAUSED", "reason": reason},
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
    if mission["plan"]["review_state"] != "approved" or not mission["plan"]["digest"]:
        raise MissionError("Mission cannot resume without an approved plan review")
    if mission["plan"]["reviewer_id"] == mission["supervisor"]["id"]:
        raise MissionError("Mission cannot resume without an independent current plan review")
    now = time.time()
    with kitty_db.connect(db_path) as conn:
        cursor = conn.execute(
            "UPDATE missions SET status='EXECUTING', status_reason=NULL, updated_at=? "
            "WHERE mission_id=? AND status='PAUSED' AND plan_review_state='approved' "
            "AND plan_reviewer_id<>supervisor_id AND plan_digest=?",
            (now, mission_id, mission["plan"]["digest"]),
        )
        if cursor.rowcount != 1:
            raise MissionError("Mission state or approved plan changed before resume")
        epoch_row = conn.execute(
            "SELECT supervisor_epoch FROM missions WHERE mission_id=?", (mission_id,)
        ).fetchone()
        _append_event(
            conn, mission_id=mission_id, event_type="mission_resumed",
            supervisor_epoch=int(epoch_row[0]), payload={"status": "EXECUTING", "reason": None},
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
    mission = assert_supervisor(
        mission_id,
        supervisor_id=supervisor_id,
        supervisor_epoch=supervisor_epoch,
        db_path=db_path,
    )
    checkpoint = dict(mission["checkpoint"])
    worker_reports = list(checkpoint.get("worker_reports") or [])
    worker_reports.append(
        {
            "worker_id": worker_id,
            "report": report,
            "evidence_locator": evidence_locator,
        }
    )
    checkpoint["worker_reports"] = worker_reports
    updated = update_checkpoint(
        mission_id,
        supervisor_id=supervisor_id,
        supervisor_epoch=supervisor_epoch,
        checkpoint=checkpoint,
        db_path=db_path,
    )
    now = time.time()
    with kitty_db.connect(db_path) as conn:
        _append_event(
            conn,
            mission_id=mission_id,
            event_type="worker_report_received",
            supervisor_epoch=supervisor_epoch,
            payload={
                "worker_id": worker_id,
                "evidence_locator": evidence_locator,
                "report": report,
            },
            now=now,
        )
        conn.commit()
    return updated
