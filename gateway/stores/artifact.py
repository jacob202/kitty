"""Durable metadata and provenance for local Kitty artifacts."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any

from gateway import db as kitty_db
from gateway.paths import KITTY_DB_FILE

ARTIFACTS_DB_FILE = KITTY_DB_FILE


class ArtifactError(RuntimeError):
    """Raised when an artifact cannot be registered or updated safely."""


def init_db() -> None:
    kitty_db.migrate(db_file=ARTIFACTS_DB_FILE)


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def register_file(
    path: Path,
    *,
    kind: str,
    media_type: str | None,
    project_id: int | None,
    created_by: str,
    source_ref: str | None = None,
    conversation_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Register an existing local file without moving or deleting it."""
    if not kind.strip():
        raise ArtifactError("artifact kind must not be empty")
    if not created_by.strip():
        raise ArtifactError("artifact created_by must not be empty")
    if project_id is not None and (isinstance(project_id, bool) or project_id <= 0):
        raise ArtifactError(f"project_id must be positive, got {project_id!r}")
    if not path.exists():
        raise ArtifactError(f"artifact source does not exist: {path}")
    if not path.is_file():
        raise ArtifactError(f"artifact source is not a file: {path}")
    content_hash, size_bytes = _hash_file(path)
    artifact_id = f"artifact_{uuid.uuid4().hex}"
    now = time.time()
    artifact = {
        "id": artifact_id,
        "project_id": project_id,
        "kind": kind,
        "media_type": media_type or "application/octet-stream",
        "display_name": path.name,
        "state": "ready",
        "storage_uri": str(path.resolve()),
        "content_hash": content_hash,
        "size_bytes": size_bytes,
        "created_at": now,
        "created_by": created_by,
        "source_ref": source_ref,
        "conversation_id": conversation_id,
        "work_item_id": None,
        "run_id": None,
        "metadata": metadata or {},
        "error": None,
    }
    init_db()
    with kitty_db.connect(ARTIFACTS_DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO artifacts
                (id, project_id, kind, media_type, display_name, state, storage_uri,
                 content_hash, size_bytes, created_at, created_by, source_ref,
                 conversation_id, work_item_id, run_id, metadata_json, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact["id"], artifact["project_id"], artifact["kind"],
                artifact["media_type"], artifact["display_name"], artifact["state"],
                artifact["storage_uri"], artifact["content_hash"], artifact["size_bytes"],
                artifact["created_at"], artifact["created_by"], artifact["source_ref"],
                artifact["conversation_id"], artifact["work_item_id"], artifact["run_id"],
                json.dumps(artifact["metadata"], ensure_ascii=False), artifact["error"],
            ),
        )
        conn.commit()
    return artifact


def update_ingestion(artifact_id: str, *, status: str, error: str | None = None) -> dict[str, Any]:
    """Record downstream ingestion state without changing file readiness."""
    if status not in {"queued", "ready", "failed"}:
        raise ArtifactError(f"invalid ingestion status {status!r}")
    init_db()
    with kitty_db.connect(ARTIFACTS_DB_FILE) as conn:
        row = conn.execute(
            "SELECT metadata_json FROM artifacts WHERE id = ?", (artifact_id,)
        ).fetchone()
        if row is None:
            raise ArtifactError(f"artifact {artifact_id} does not exist")
        try:
            metadata = json.loads(row["metadata_json"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise ArtifactError(f"artifact {artifact_id} has corrupt metadata: {exc}") from exc
        if not isinstance(metadata, dict):
            raise ArtifactError(f"artifact {artifact_id} metadata is not an object")
        metadata["ingestion_status"] = status
        if error is not None:
            metadata["ingestion_error"] = error
        conn.execute(
            "UPDATE artifacts SET metadata_json = ? WHERE id = ?",
            (json.dumps(metadata, ensure_ascii=False), artifact_id),
        )
        conn.commit()
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ArtifactError(f"artifact {artifact_id} disappeared after ingestion update")
    return artifact


def get_artifact(artifact_id: str) -> dict[str, Any] | None:
    init_db()
    with kitty_db.connect(ARTIFACTS_DB_FILE) as conn:
        row = conn.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
    return _row_to_artifact(row) if row is not None else None


def list_artifacts(
    *,
    project_id: int | None = None,
    conversation_id: str | None = None,
    kind: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    if limit <= 0 or limit > 500:
        raise ArtifactError(f"limit must be between 1 and 500, got {limit}")
    if project_id is not None and (isinstance(project_id, bool) or project_id <= 0):
        raise ArtifactError(f"project_id must be positive, got {project_id!r}")
    init_db()
    clauses: list[str] = []
    params: list[Any] = []
    if project_id is not None:
        clauses.append("project_id = ?")
        params.append(project_id)
    if conversation_id is not None:
        clauses.append("conversation_id = ?")
        params.append(conversation_id)
    if kind is not None:
        clauses.append("kind = ?")
        params.append(kind)
    where = " AND ".join(clauses) if clauses else "1 = 1"
    params.append(limit)
    with kitty_db.connect(ARTIFACTS_DB_FILE) as conn:
        rows = conn.execute(
            f"SELECT * FROM artifacts WHERE {where} ORDER BY created_at DESC, id DESC LIMIT ?",
            params,
        ).fetchall()
    return [_row_to_artifact(row) for row in rows]


def _row_to_artifact(row: Any) -> dict[str, Any]:
    result = dict(row)
    try:
        result["metadata"] = json.loads(result.pop("metadata_json"))
    except (TypeError, json.JSONDecodeError) as exc:
        raise ArtifactError(f"artifact {result.get('id')} has corrupt metadata: {exc}") from exc
    return result
