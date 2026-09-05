"""KX-COORD-01: SQLite-enforced mutation ownership for Kitty agents.

SQLite is authoritative for ownership. The tracked semantic registry defines
claimable resources; GAR is a best-effort event projection only.
"""
from __future__ import annotations

import fnmatch
import json
import sqlite3
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import yaml

from gateway import agent_workspace
from gateway.paths import ROOT

MUTATING_ROLES = frozenset({"OWN", "INTEGRATE"})
READ_ONLY_ROLES = frozenset({"REVIEW", "RESEARCH"})
VALID_ROLES = MUTATING_ROLES | READ_ONLY_ROLES
DEFAULT_LEASE_SECONDS = 45 * 60
DEFAULT_REGISTRY_PATH = ROOT / "coordination" / "resources.yaml"
DB_FILENAME = ".kitty-coordination.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    participant TEXT,
    role TEXT NOT NULL CHECK (role IN ('OWN','REVIEW','INTEGRATE','RESEARCH')),
    resource_id TEXT NOT NULL,
    lane TEXT,
    task_id TEXT,
    branch TEXT,
    worktree TEXT,
    base_sha TEXT NOT NULL,
    paths_json TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('active','released','expired','forced'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_claims_active_mutator_resource
    ON claims(resource_id)
    WHERE state = 'active' AND role IN ('OWN','INTEGRATE');
CREATE INDEX IF NOT EXISTS idx_claims_session_state ON claims(session_id, state);
CREATE INDEX IF NOT EXISTS idx_claims_expiry ON claims(state, expires_at);
"""


class CoordinationClaimError(RuntimeError):
    """A claim request is invalid or cannot be evaluated safely."""


def _required_text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def _utc(value: str | datetime | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"invalid timestamp {value!r}") from exc
    else:
        raise TypeError("timestamp must be an ISO string, datetime, or None")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _stamp(value: str | datetime | None = None) -> str:
    return _utc(value).isoformat(timespec="microseconds")


def _normalize_repo_path(value: str) -> str:
    raw = _required_text(value, "path").replace("\\", "/")
    while raw.startswith("./"):
        raw = raw[2:]
    candidate = PurePosixPath(raw)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise ValueError(f"path must be repo-relative and normalized: {value!r}")
    return candidate.as_posix()


def _normalize_pattern(value: str) -> str:
    raw = _required_text(value, "path pattern").replace("\\", "/")
    while raw.startswith("./"):
        raw = raw[2:]
    if raw.startswith("/") or any(part == ".." for part in PurePosixPath(raw).parts):
        raise ValueError(f"path pattern must be repo-relative: {value!r}")
    return raw


def _normalize_paths(values: Iterable[str]) -> list[str]:
    return sorted({_normalize_pattern(value) for value in values})


def _pattern_matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return path == prefix or path.startswith(prefix + "/")
    return fnmatch.fnmatchcase(path, pattern)


def _load_registry(registry_path: Path | None = None) -> dict[str, list[str]]:
    path = Path(registry_path or DEFAULT_REGISTRY_PATH)
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CoordinationClaimError(f"cannot read coordination registry {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise CoordinationClaimError(f"invalid coordination registry {path}: {exc}") from exc
    if not isinstance(payload, dict) or set(payload) != {"resources"}:
        raise CoordinationClaimError("coordination registry must contain only a resources mapping")
    raw_resources = payload["resources"]
    if not isinstance(raw_resources, dict) or not raw_resources:
        raise CoordinationClaimError("coordination registry resources must be a non-empty mapping")

    resources: dict[str, list[str]] = {}
    for resource_id, spec in raw_resources.items():
        if not isinstance(resource_id, str) or not resource_id.strip():
            raise CoordinationClaimError("coordination resource IDs must be non-empty strings")
        if not isinstance(spec, dict) or set(spec) != {"paths"}:
            raise CoordinationClaimError(f"resource {resource_id} must contain only paths")
        raw_paths = spec["paths"]
        if not isinstance(raw_paths, list) or not raw_paths:
            raise CoordinationClaimError(f"resource {resource_id} paths must be a non-empty list")
        if not all(isinstance(item, str) for item in raw_paths):
            raise CoordinationClaimError(f"resource {resource_id} paths must contain strings")
        normalized = _normalize_paths(raw_paths)
        if normalized != raw_paths:
            raise CoordinationClaimError(
                f"resource {resource_id} paths must be sorted and contain no duplicates"
            )
        resources[resource_id] = normalized
    return resources


def _normalize_scope(value: str) -> str:
    raw = _required_text(value, "scope").replace("\\", "/")
    while raw.startswith("./"):
        raw = raw[2:]
    if raw == ".":
        return raw
    raw = raw.rstrip("/")
    candidate = PurePosixPath(raw)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise ValueError(f"scope must be repo-relative and bounded: {value!r}")
    return candidate.as_posix()


def _scope_overlaps_pattern(scope: str, pattern: str) -> bool:
    if scope == ".":
        return True
    if _pattern_matches(scope, pattern):
        return True
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return (
            scope == prefix
            or scope.startswith(prefix + "/")
            or prefix.startswith(scope + "/")
        )
    wildcard_positions = [
        index for token in "*?[" if (index := pattern.find(token)) >= 0
    ]
    if not wildcard_positions:
        return pattern.startswith(scope + "/")
    literal_prefix = pattern[: min(wildcard_positions)].rstrip("/")
    if not literal_prefix:
        return True
    return (
        scope == literal_prefix
        or scope.startswith(literal_prefix + "/")
        or literal_prefix.startswith(scope + "/")
    )


def resolve_scopes_to_resources(
    scopes: Iterable[str], *, registry_path: Path | None = None
) -> list[str]:
    """Resolve Builder-style prefix scopes to every semantic resource they can overlap."""
    registry = _load_registry(registry_path)
    normalized_scopes = sorted({_normalize_scope(scope) for scope in scopes})
    return sorted(
        resource_id
        for resource_id, patterns in registry.items()
        if any(
            _scope_overlaps_pattern(scope, pattern)
            for scope in normalized_scopes
            for pattern in patterns
        )
    )


def resolve_paths_to_resources(
    paths: Iterable[str], *, registry_path: Path | None = None
) -> list[str]:
    """Resolve repo-relative paths to deterministic registered semantic IDs."""
    registry = _load_registry(registry_path)
    normalized_paths = sorted({_normalize_repo_path(path) for path in paths})
    resolved = {
        resource_id
        for resource_id, patterns in registry.items()
        if any(
            _pattern_matches(path, pattern)
            for path in normalized_paths
            for pattern in patterns
        )
    }
    return sorted(resolved)


def canonical_repo_root(cwd: Path | None = None) -> Path:
    """Return the shared root, not the linked worktree root."""
    start = Path(cwd or ROOT).resolve()
    result = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--path-format=absolute", "--git-common-dir"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        common = Path(result.stdout.strip()).resolve()
        if common.name == ".git":
            return common.parent
    return start


def default_db_path() -> Path:
    return canonical_repo_root() / DB_FILENAME


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path or default_db_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    last_error: sqlite3.OperationalError | None = None
    for attempt in range(8):
        conn = sqlite3.connect(path, timeout=15, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA busy_timeout = 15000")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.executescript(_SCHEMA)
            return conn
        except sqlite3.OperationalError as exc:
            conn.close()
            if "locked" not in str(exc).lower():
                raise
            last_error = exc
            if attempt == 7:
                break
            time.sleep(min(0.02 * (2**attempt), 0.25))
    assert last_error is not None
    raise last_error


def _decode(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    claim = dict(row)
    claim["paths"] = json.loads(claim.pop("paths_json"))
    return claim


def _validate_base_sha(base_sha: str) -> str:
    value = _required_text(base_sha, "base_sha")
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("base_sha must be a full lowercase 40-character Git SHA")
    return value


def _project_event(
    event: str,
    *,
    participant: str | None,
    claim: dict[str, Any] | None = None,
    holder: dict[str, Any] | None = None,
    reason: str | None = None,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sender = participant or (claim or {}).get("participant") or "chatgpt"
    lines = [f"COORDINATION {event}"]
    if claim:
        lines.append(
            f"session={claim['session_id']} role={claim['role']} resource={claim['resource_id']}"
        )
        lines.append(
            f"branch={claim.get('branch') or '-'} worktree={claim.get('worktree') or '-'}"
        )
        lines.append(f"expires_at={claim['expires_at']} state={claim['state']}")
    if holder:
        lines.append(
            f"holder={holder['session_id']} role={holder['role']} "
            f"branch={holder.get('branch') or '-'} expires_at={holder['expires_at']}"
        )
    if previous:
        lines.append(
            f"previous_session={previous['session_id']} previous_role={previous['role']}"
        )
    if reason:
        lines.append(f"reason={reason}")
    try:
        message = agent_workspace.post_global_message(
            sender_id=sender,
            content="\n".join(lines),
            message_kind="result" if event == "CLAIM RELEASED" else "status",
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "message_id": message["id"]}


def _expire_rows(conn: sqlite3.Connection, now_stamp: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM claims WHERE state='active' AND expires_at <= ? "
        "ORDER BY created_at, id",
        (now_stamp,),
    ).fetchall()
    if rows:
        conn.execute(
            "UPDATE claims SET state='expired' WHERE state='active' AND expires_at <= ?",
            (now_stamp,),
        )
    return [_decode(row) | {"state": "expired"} for row in rows]


def acquire(
    *,
    session_id: str,
    role: str,
    resource_id: str,
    base_sha: str,
    paths: Iterable[str],
    participant: str | None = None,
    lane: str | None = None,
    task_id: str | None = None,
    branch: str | None = None,
    worktree: str | None = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    db_path: Path | None = None,
    registry_path: Path | None = None,
    now: str | datetime | None = None,
) -> dict[str, Any]:
    """Acquire one semantic claim; SQLite's partial unique index is the mutex."""
    session = _required_text(session_id, "session_id")
    role = _required_text(role, "role").upper()
    if role not in VALID_ROLES:
        raise ValueError(f"role must be one of {sorted(VALID_ROLES)}")
    resource = _required_text(resource_id, "resource_id")
    registry = _load_registry(registry_path)
    if resource not in registry:
        raise CoordinationClaimError(f"resource_id {resource!r} is not registered")
    base = _validate_base_sha(base_sha)
    normalized_paths = _normalize_paths(paths)
    if role in MUTATING_ROLES and not normalized_paths:
        raise ValueError("OWN and INTEGRATE claims require declared paths")
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive")

    created = _utc(now)
    created_stamp = _stamp(created)
    expires_stamp = _stamp(created + timedelta(seconds=lease_seconds))
    claim_id = f"claim_{uuid.uuid4().hex}"
    conn = _connect(db_path)
    expired: list[dict[str, Any]] = []
    holder: dict[str, Any] | None = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        expired = _expire_rows(conn, created_stamp)
        try:
            conn.execute(
                "INSERT INTO claims "
                "(id,session_id,participant,role,resource_id,lane,task_id,branch,worktree,"
                "base_sha,paths_json,created_at,expires_at,state) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'active')",
                (
                    claim_id, session, participant, role, resource, lane, task_id,
                    branch, worktree, base,
                    json.dumps(normalized_paths, separators=(",", ":")),
                    created_stamp, expires_stamp,
                ),
            )
        except sqlite3.IntegrityError:
            holder_row = conn.execute(
                "SELECT * FROM claims WHERE resource_id=? AND state='active' "
                "AND role IN ('OWN','INTEGRATE') ORDER BY created_at,id LIMIT 1",
                (resource,),
            ).fetchone()
            if holder_row is None:
                conn.rollback()
                raise
            holder = _decode(holder_row)
            conn.commit()
        else:
            row = conn.execute("SELECT * FROM claims WHERE id=?", (claim_id,)).fetchone()
            conn.commit()
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()

    for stale in expired:
        _project_event("LEASE STALE", participant=stale.get("participant"), claim=stale)
    if holder is not None:
        projection = _project_event(
            "CLAIM CONFLICT", participant=participant, holder=holder,
            reason=f"resource {resource} is already owned",
        )
        return {"status": "CONFLICT", "holder": holder, "gar_projection": projection}
    if row is None:
        raise CoordinationClaimError("claim was inserted but could not be read back")
    claim = _decode(row)
    previous = next(
        (
            item for item in reversed(expired)
            if item["resource_id"] == resource and item["role"] in MUTATING_ROLES
        ),
        None,
    )
    transfer_projection = None
    if previous is not None and role in MUTATING_ROLES:
        transfer_projection = _project_event(
            "OWNERSHIP TRANSFERRED",
            participant=participant,
            claim=claim,
            previous=previous,
        )
    acquired_projection = _project_event(
        "CLAIM ACQUIRED", participant=participant, claim=claim
    )
    return {
        "status": "ACQUIRED",
        "claim": claim,
        "gar_projection": acquired_projection,
        "transfer_projection": transfer_projection,
    }


def acquire_many(
    session_id: str,
    *,
    role: str,
    resource_ids: Iterable[str],
    base_sha: str,
    paths: Iterable[str],
    participant: str | None = None,
    lane: str | None = None,
    task_id: str | None = None,
    branch: str | None = None,
    worktree: str | None = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    db_path: Path | None = None,
    registry_path: Path | None = None,
    now: str | datetime | None = None,
) -> dict[str, Any]:
    """Atomically acquire a complete semantic resource set or none of it."""
    session = _required_text(session_id, "session_id")
    normalized_role = _required_text(role, "role").upper()
    if normalized_role not in VALID_ROLES:
        raise ValueError(f"role must be one of {sorted(VALID_ROLES)}")
    resources = sorted({_required_text(item, "resource_id") for item in resource_ids})
    if not resources:
        raise ValueError("resource_ids must be non-empty")
    registry = _load_registry(registry_path)
    unknown = [resource for resource in resources if resource not in registry]
    if unknown:
        raise CoordinationClaimError(
            "unregistered resource_id(s): " + ", ".join(unknown)
        )
    base = _validate_base_sha(base_sha)
    normalized_paths = _normalize_paths(paths)
    if normalized_role in MUTATING_ROLES and not normalized_paths:
        raise ValueError("OWN and INTEGRATE claims require declared paths")
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive")

    created = _utc(now)
    created_stamp = _stamp(created)
    expires_stamp = _stamp(created + timedelta(seconds=lease_seconds))
    conn = _connect(db_path)
    expired: list[dict[str, Any]] = []
    holders: list[dict[str, Any]] = []
    rows: list[sqlite3.Row] = []
    try:
        conn.execute("BEGIN IMMEDIATE")
        expired = _expire_rows(conn, created_stamp)
        if normalized_role in MUTATING_ROLES:
            placeholders = ",".join("?" for _ in resources)
            holder_rows = conn.execute(
                f"SELECT * FROM claims WHERE state='active' "
                f"AND role IN ('OWN','INTEGRATE') AND resource_id IN ({placeholders}) "
                "ORDER BY resource_id,created_at,id",
                resources,
            ).fetchall()
            holders = [_decode(row) for row in holder_rows]
        if holders:
            conn.commit()
        else:
            claim_ids: list[str] = []
            for resource in resources:
                claim_id = f"claim_{uuid.uuid4().hex}"
                claim_ids.append(claim_id)
                conn.execute(
                    "INSERT INTO claims "
                    "(id,session_id,participant,role,resource_id,lane,task_id,branch,worktree,"
                    "base_sha,paths_json,created_at,expires_at,state) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'active')",
                    (
                        claim_id, session, participant, normalized_role, resource, lane, task_id,
                        branch, worktree, base,
                        json.dumps(normalized_paths, separators=(",", ":")),
                        created_stamp, expires_stamp,
                    ),
                )
            placeholders = ",".join("?" for _ in claim_ids)
            rows = conn.execute(
                f"SELECT * FROM claims WHERE id IN ({placeholders}) ORDER BY resource_id,id",
                claim_ids,
            ).fetchall()
            conn.commit()
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()

    for stale in expired:
        _project_event("LEASE STALE", participant=stale.get("participant"), claim=stale)
    if holders:
        projection = _project_event(
            "CLAIM CONFLICT", participant=participant, holder=holders[0],
            reason="requested resource set conflicts with active ownership",
        )
        return {"status": "CONFLICT", "holders": holders, "gar_projection": projection}

    claims = [_decode(row) for row in rows]
    transfer_projections = []
    if normalized_role in MUTATING_ROLES:
        for claim in claims:
            previous = next(
                (
                    item for item in reversed(expired)
                    if item["resource_id"] == claim["resource_id"]
                    and item["role"] in MUTATING_ROLES
                ),
                None,
            )
            if previous is not None:
                transfer_projections.append(
                    _project_event(
                        "OWNERSHIP TRANSFERRED",
                        participant=participant,
                        claim=claim,
                        previous=previous,
                    )
                )
    projections = [
        _project_event("CLAIM ACQUIRED", participant=participant, claim=claim)
        for claim in claims
    ]
    return {
        "status": "ACQUIRED",
        "claims": claims,
        "gar_projections": projections,
        "transfer_projections": transfer_projections,
    }


def renew(
    session_id: str,
    *,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    db_path: Path | None = None,
    now: str | datetime | None = None,
) -> dict[str, Any]:
    session = _required_text(session_id, "session_id")
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive")
    current = _utc(now)
    stamp = _stamp(current)
    expires = _stamp(current + timedelta(seconds=lease_seconds))
    conn = _connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        expired = _expire_rows(conn, stamp)
        cursor = conn.execute(
            "UPDATE claims SET expires_at=? WHERE session_id=? AND state='active'",
            (expires, session),
        )
        rows = conn.execute(
            "SELECT * FROM claims WHERE session_id=? AND state='active' "
            "ORDER BY resource_id,id",
            (session,),
        ).fetchall()
        conn.commit()
    finally:
        conn.close()
    for stale in expired:
        _project_event("LEASE STALE", participant=stale.get("participant"), claim=stale)
    if cursor.rowcount == 0:
        raise CoordinationClaimError(f"session {session} has no active claim to renew")
    return {"renewed": cursor.rowcount, "claims": [_decode(row) for row in rows]}


def release(
    session_id: str,
    *,
    db_path: Path | None = None,
    now: str | datetime | None = None,
) -> dict[str, Any]:
    session = _required_text(session_id, "session_id")
    stamp = _stamp(now)
    conn = _connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        expired = _expire_rows(conn, stamp)
        rows = conn.execute(
            "SELECT * FROM claims WHERE session_id=? AND state='active' "
            "ORDER BY resource_id,id",
            (session,),
        ).fetchall()
        cursor = conn.execute(
            "UPDATE claims SET state='released' WHERE session_id=? AND state='active'",
            (session,),
        )
        conn.commit()
    finally:
        conn.close()
    for stale in expired:
        _project_event("LEASE STALE", participant=stale.get("participant"), claim=stale)
    projections = []
    for row in rows:
        claim = _decode(row) | {"state": "released"}
        projections.append(
            _project_event("CLAIM RELEASED", participant=claim.get("participant"), claim=claim)
        )
    return {"released": cursor.rowcount, "gar_projections": projections}


def force_release(
    session_id: str,
    reason: str,
    *,
    participant: str | None = None,
    db_path: Path | None = None,
    now: str | datetime | None = None,
) -> dict[str, Any]:
    session = _required_text(session_id, "session_id")
    reason = _required_text(reason, "reason")
    stamp = _stamp(now)
    conn = _connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        expired = _expire_rows(conn, stamp)
        rows = conn.execute(
            "SELECT * FROM claims WHERE session_id=? AND state='active' ORDER BY resource_id,id",
            (session,),
        ).fetchall()
        cursor = conn.execute(
            "UPDATE claims SET state=? WHERE session_id=? AND state='active'",
            ("forced", session),
        )
        conn.commit()
    finally:
        conn.close()
    for stale in expired:
        _project_event("LEASE STALE", participant=stale.get("participant"), claim=stale)
    projections = []
    for row in rows:
        claim = _decode(row) | {"state": "forced"}
        projections.append(
            _project_event(
                "FORCE RELEASE",
                participant=participant or claim.get("participant"),
                claim=claim,
                reason=reason,
            )
        )
    return {"released": cursor.rowcount, "gar_projections": projections}


def _expire_and_project(
    *, db_path: Path | None, now: str | datetime | None
) -> str:
    stamp = _stamp(now)
    conn = _connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        expired = _expire_rows(conn, stamp)
        conn.commit()
    finally:
        conn.close()
    for stale in expired:
        _project_event("LEASE STALE", participant=stale.get("participant"), claim=stale)
    return stamp


def list_claims(
    *,
    active_only: bool = False,
    db_path: Path | None = None,
    now: str | datetime | None = None,
) -> list[dict[str, Any]]:
    stamp = _expire_and_project(db_path=db_path, now=now)
    conn = _connect(db_path)
    try:
        if active_only:
            rows = conn.execute(
                "SELECT * FROM claims WHERE state='active' AND expires_at>? "
                "ORDER BY resource_id,created_at,id",
                (stamp,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM claims ORDER BY created_at,id"
            ).fetchall()
    finally:
        conn.close()
    return [_decode(row) for row in rows]


def preflight_mutation(
    session_id: str,
    staged_paths: Iterable[str],
    *,
    db_path: Path | None = None,
    registry_path: Path | None = None,
    now: str | datetime | None = None,
    required_role: str | None = None,
) -> dict[str, Any]:
    """Fail closed unless live mutating claims cover every path and semantic ID."""
    session = _required_text(session_id, "session_id")
    paths = sorted({_normalize_repo_path(path) for path in staged_paths})
    stamp = _expire_and_project(db_path=db_path, now=now)
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM claims WHERE session_id=? AND state='active' AND expires_at>? "
            "ORDER BY resource_id,created_at,id",
            (session, stamp),
        ).fetchall()
    finally:
        conn.close()
    claims = [_decode(row) for row in rows]
    if not claims:
        return {"ok": False, "reason": f"session {session} has no active claim"}

    role_filter = required_role.upper() if required_role else None
    if role_filter is not None and role_filter not in MUTATING_ROLES:
        raise ValueError("required_role must be OWN or INTEGRATE")
    mutating = [
        claim for claim in claims
        if claim["role"] in MUTATING_ROLES
        and (role_filter is None or claim["role"] == role_filter)
    ]
    if not mutating:
        if role_filter:
            return {
                "ok": False,
                "reason": f"mutation requires active {role_filter} ownership for this checkout",
            }
        return {"ok": False, "reason": "mutation role must be OWN or INTEGRATE"}

    for path in paths:
        if not any(
            _pattern_matches(path, pattern)
            for claim in mutating
            for pattern in claim["paths"]
        ):
            return {
                "ok": False,
                "reason": f"staged path {path} is outside the declared path fence",
            }

    claimed_resources = {claim["resource_id"] for claim in mutating}
    for path in paths:
        resolved = resolve_paths_to_resources([path], registry_path=registry_path)
        if not resolved:
            return {
                "ok": False,
                "reason": f"staged path {path} resolves to no registered semantic resource",
            }
        missing = sorted(set(resolved) - claimed_resources)
        if missing:
            return {
                "ok": False,
                "reason": (
                    f"staged path {path} resolves to unclaimed semantic resource(s): "
                    + ", ".join(missing)
                ),
            }
    return {
        "ok": True,
        "session_id": session,
        "paths": paths,
        "resources": sorted(claimed_resources),
        "roles": sorted({claim["role"] for claim in mutating}),
    }
