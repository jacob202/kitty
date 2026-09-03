"""Atomic interactive ownership claims for concurrent Kitty agents.

This module is a mutation-safety primitive only. It does not choose work or
replace KittyBuilder. Claims serialize interactive ownership in Kitty's normal
state database so supported agents can fail closed before overlapping edits.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from gateway import db as kitty_db
from gateway.paths import BUILDER_QUEUE_DB, KITTY_DB_FILE

MUTATING_ROLES = frozenset({"OWN", "INTEGRATE"})
READ_ONLY_ROLES = frozenset({"REVIEW", "RESEARCH"})
VALID_ROLES = MUTATING_ROLES | READ_ONLY_ROLES


class CoordinationClaimError(RuntimeError):
    """Raised when a claim cannot safely authorize an operation."""


class CoordinationConflictError(CoordinationClaimError):
    """Raised when requested ownership overlaps a live mutating claim."""


def _required(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def _normalize_worktree(value: str) -> str:
    return str(Path(_required(value, "worktree_path")).expanduser().resolve())


def _normalize_path(value: str) -> str:
    raw = _required(value, "path").replace("\\", "/")
    while raw.startswith("./"):
        raw = raw[2:]
    candidate = PurePosixPath(raw)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise ValueError(f"path must be a normalized repo-relative path: {value}")
    return candidate.as_posix()


def _normalize_resource(value: str) -> str:
    return _required(value, "resource").lower()


def _normalized_unique(values: Iterable[str], normalizer) -> list[str]:
    return sorted({normalizer(value) for value in values})


def _path_overlap(left: str, right: str) -> bool:
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def _decode(row: Any) -> dict[str, Any]:
    claim = dict(row)
    claim["paths"] = json.loads(claim.pop("paths_json"))
    claim["resources"] = json.loads(claim.pop("resources_json"))
    return claim


def _init(db_path: Path | None) -> Path:
    path = Path(db_path) if db_path is not None else KITTY_DB_FILE
    kitty_db.migrate(db_file=path)
    return path


def _active_rows(conn, now: float) -> list[Any]:
    return conn.execute(
        """
        SELECT * FROM agent_coordination_claims
        WHERE released_at IS NULL AND lease_expires_at > ?
        ORDER BY created_at ASC, claim_id ASC
        """,
        (now,),
    ).fetchall()


def list_builder_claims(*, builder_db_path: Path | None = None) -> list[dict[str, Any]]:
    """Project active Builder branch leases into coordination without mutating Builder."""
    database = Path(builder_db_path) if builder_db_path is not None else BUILDER_QUEUE_DB
    if not database.exists():
        return []
    uri = f"file:{database.resolve()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT l.initiative_id, l.packet_id, l.worker_id, l.branch,
                   l.worktree_path, l.base_sha, p.task_id,
                   p.allowed_paths_json, t.state
            FROM branch_leases AS l
            LEFT JOIN initiative_packets AS p
              ON p.initiative_id = l.initiative_id AND p.packet_id = l.packet_id
            LEFT JOIN tasks AS t ON t.id = p.task_id
            WHERE t.state IS NULL OR t.state NOT IN ('done', 'failed', 'cancelled')
            ORDER BY l.initiative_id ASC, l.packet_id ASC
            """
        ).fetchall()
    except sqlite3.Error as exc:
        raise CoordinationClaimError(f"cannot read Builder ownership projection: {exc}") from exc
    finally:
        try:
            conn.close()
        except UnboundLocalError:
            pass

    projected: list[dict[str, Any]] = []
    for row in rows:
        state = row["state"] or "unknown"
        worktree_path = Path(row["worktree_path"]).expanduser().resolve()
        # Builder can retain historical branch-lease rows after a blocked/queued
        # worktree has been intentionally retired. Those rows are evidence, not
        # live mutation ownership. Preserve active execution states fail-closed,
        # but do not let an absent recoverable worktree freeze broad path fences.
        if state in {"blocked", "queued"} and not worktree_path.exists():
            continue
        raw_paths = row["allowed_paths_json"]
        try:
            paths = json.loads(raw_paths) if raw_paths else []
        except json.JSONDecodeError as exc:
            raise CoordinationClaimError(
                f"Builder {row['initiative_id']}/{row['packet_id']} has invalid allowed_paths_json"
            ) from exc
        if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
            raise CoordinationClaimError(
                f"Builder {row['initiative_id']}/{row['packet_id']} has invalid allowed paths"
            )
        projected.append(
            {
                "source": "builder",
                "participant_id": row["worker_id"],
                "session_id": row["task_id"] or f"builder:{row['initiative_id']}/{row['packet_id']}",
                "role": "OWN",
                "lane_id": f"{row['initiative_id']}/{row['packet_id']}",
                "initiative_id": row["initiative_id"],
                "packet_id": row["packet_id"],
                "task_id": row["task_id"],
                "state": state,
                "base_sha": row["base_sha"],
                "branch": row["branch"],
                "worktree_path": str(worktree_path),
                "paths": _normalized_unique(paths, _normalize_path),
                "resources": [
                    _normalize_resource(f"builder:{row['initiative_id']}/{row['packet_id']}")
                ],
            }
        )
    return projected


def _conflict(existing: dict[str, Any], paths: list[str], resources: list[str]) -> str | None:
    resource_overlap = sorted(set(existing["resources"]) & set(resources))
    if resource_overlap:
        return f"semantic resource {resource_overlap[0]}"
    for requested in paths:
        for held in existing["paths"]:
            if _path_overlap(requested, held):
                return f"path {requested} overlaps {held}"
    return None


def claim(
    *,
    participant_id: str,
    session_id: str,
    role: str,
    lane_id: str,
    base_sha: str,
    branch: str,
    worktree_path: str,
    paths: Iterable[str],
    resources: Iterable[str] = (),
    lease_seconds: int = 1800,
    db_path: Path | None = None,
    builder_db_path: Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    participant_id = _required(participant_id, "participant_id")
    session_id = _required(session_id, "session_id")
    lane_id = _required(lane_id, "lane_id")
    branch = _required(branch, "branch")
    role = _required(role, "role").upper()
    if role not in VALID_ROLES:
        raise ValueError(f"role must be one of {sorted(VALID_ROLES)}")
    if len(base_sha) != 40 or any(ch not in "0123456789abcdef" for ch in base_sha):
        raise ValueError("base_sha must be a full lowercase 40-character Git SHA")
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive")

    worktree = _normalize_worktree(worktree_path)
    normalized_paths = _normalized_unique(paths, _normalize_path)
    normalized_resources = _normalized_unique(resources, _normalize_resource)
    if role in MUTATING_ROLES and not normalized_paths:
        raise ValueError("mutating claims require at least one path")

    timestamp = time.time() if now is None else float(now)
    expires = timestamp + lease_seconds
    claim_id = f"claim_{uuid.uuid4().hex}"
    database = _init(db_path)
    conn = kitty_db.connect(database)
    try:
        conn.execute("BEGIN IMMEDIATE")
        active = [_decode(row) for row in _active_rows(conn, timestamp)]
        if role in MUTATING_ROLES:
            for builder_claim in list_builder_claims(builder_db_path=builder_db_path):
                reason = _conflict(builder_claim, normalized_paths, normalized_resources)
                same_worktree = builder_claim["worktree_path"] == worktree
                if reason or same_worktree:
                    detail = reason or f"worktree {worktree}"
                    raise CoordinationConflictError(
                        f"claim conflicts with Builder {builder_claim['initiative_id']}/{builder_claim['packet_id']}: {detail}"
                    )
        for existing in active:
            if existing["session_id"] == session_id:
                raise CoordinationConflictError(
                    f"session {session_id} already holds live claim {existing['claim_id']}"
                )
            if existing["worktree_path"] == worktree and existing["role"] in MUTATING_ROLES:
                raise CoordinationConflictError(
                    f"worktree {worktree} already has live mutating claim {existing['claim_id']}"
                )
            if role in MUTATING_ROLES and existing["role"] in MUTATING_ROLES:
                reason = _conflict(existing, normalized_paths, normalized_resources)
                if reason:
                    raise CoordinationConflictError(
                        f"claim conflicts with {existing['participant_id']}/{existing['lane_id']}: {reason}"
                    )
        conn.execute(
            """
            INSERT INTO agent_coordination_claims
                (claim_id, participant_id, session_id, role, lane_id, base_sha,
                 branch, worktree_path, paths_json, resources_json, created_at,
                 heartbeat_at, lease_expires_at, released_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                claim_id,
                participant_id,
                session_id,
                role,
                lane_id,
                base_sha,
                branch,
                worktree,
                json.dumps(normalized_paths),
                json.dumps(normalized_resources),
                timestamp,
                timestamp,
                expires,
            ),
        )
        row = conn.execute(
            "SELECT * FROM agent_coordination_claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    if row is None:
        raise RuntimeError("claim inserted but not retrievable")
    return _decode(row)


def list_claims(*, active_only: bool = True, db_path: Path | None = None, now: float | None = None) -> list[dict[str, Any]]:
    timestamp = time.time() if now is None else float(now)
    database = _init(db_path)
    with kitty_db.connect(database) as conn:
        if active_only:
            rows = _active_rows(conn, timestamp)
        else:
            rows = conn.execute(
                "SELECT * FROM agent_coordination_claims ORDER BY created_at ASC, claim_id ASC"
            ).fetchall()
    return [_decode(row) for row in rows]


def renew(claim_id: str, session_id: str, *, lease_seconds: int = 1800, db_path: Path | None = None, now: float | None = None) -> dict[str, Any]:
    claim_id = _required(claim_id, "claim_id")
    session_id = _required(session_id, "session_id")
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive")
    timestamp = time.time() if now is None else float(now)
    database = _init(db_path)
    with kitty_db.connect(database) as conn:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            """
            UPDATE agent_coordination_claims
            SET heartbeat_at = ?, lease_expires_at = ?
            WHERE claim_id = ? AND session_id = ? AND released_at IS NULL
              AND lease_expires_at > ?
            """,
            (timestamp, timestamp + lease_seconds, claim_id, session_id, timestamp),
        )
        if cursor.rowcount != 1:
            raise CoordinationClaimError("claim is missing, expired, released, or owned by another session")
        row = conn.execute("SELECT * FROM agent_coordination_claims WHERE claim_id = ?", (claim_id,)).fetchone()
        conn.commit()
    return _decode(row)


def release(claim_id: str, session_id: str, *, db_path: Path | None = None, now: float | None = None) -> dict[str, Any]:
    claim_id = _required(claim_id, "claim_id")
    session_id = _required(session_id, "session_id")
    timestamp = time.time() if now is None else float(now)
    database = _init(db_path)
    with kitty_db.connect(database) as conn:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            """
            UPDATE agent_coordination_claims SET released_at = ?, heartbeat_at = ?
            WHERE claim_id = ? AND session_id = ? AND released_at IS NULL
            """,
            (timestamp, timestamp, claim_id, session_id),
        )
        if cursor.rowcount != 1:
            raise CoordinationClaimError("claim is missing, released, or owned by another session")
        row = conn.execute("SELECT * FROM agent_coordination_claims WHERE claim_id = ?", (claim_id,)).fetchone()
        conn.commit()
    return _decode(row)


def guard_paths(worktree_path: str, paths: Iterable[str], *, db_path: Path | None = None, now: float | None = None) -> dict[str, Any]:
    timestamp = time.time() if now is None else float(now)
    worktree = _normalize_worktree(worktree_path)
    requested = _normalized_unique(paths, _normalize_path)
    if not requested:
        raise CoordinationClaimError("no mutation paths supplied")
    database = _init(db_path)
    with kitty_db.connect(database) as conn:
        rows = conn.execute(
            """
            SELECT * FROM agent_coordination_claims
            WHERE worktree_path = ? AND released_at IS NULL AND lease_expires_at > ?
              AND role IN ('OWN', 'INTEGRATE')
            ORDER BY created_at DESC
            """,
            (worktree, timestamp),
        ).fetchall()
    if len(rows) != 1:
        raise CoordinationClaimError(
            f"worktree has {len(rows)} live mutating claims; exactly one is required"
        )
    authorizing = _decode(rows[0])
    uncovered = [
        path for path in requested
        if not any(path == held or path.startswith(held + "/") for held in authorizing["paths"])
    ]
    if uncovered:
        raise CoordinationClaimError(
            "mutation path outside claim scope: " + ", ".join(uncovered)
        )
    return {"claim": authorizing, "paths": requested}
