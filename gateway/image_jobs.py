"""Durable provider-neutral image-job metadata store (IMG-01).

Kitty's legacy Image Lab (gateway/image_gen.py) kept only an in-memory list of
recent jobs, so seeds and outputs were lost on restart. This store persists
every job in Kitty's SQLite database with a normalized, provider-neutral schema
so later packets (cancellation, atomic persistence, lineage, convergence) can
build on it.

Design boundaries:
- API-only to ComfyUI (GPL-3.0): we never store the executable workflow graph,
  only a template name/hash for reproducibility.
- provider_params is a bounded JSON blob for backend-specific extras.
- All status transitions are validated and applied in a single transaction.

Ported from PR #210's richer design: TEXT job_id (UUID), 6-state lifecycle,
updated_at/finished_at timestamps, workflow_hash, normalization functions,
and bounded error/text fields.
"""

from __future__ import annotations

import json
import mimetypes
import uuid
from dataclasses import dataclass
from dataclasses import fields as dc_fields
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from gateway import db as kitty_db
from gateway import paths as _paths
from gateway.paths import DB_MIGRATIONS_DIR

_MIGRATION_FILE = DB_MIGRATIONS_DIR / "023_image_jobs.sql"

# Per-process memo of DB paths whose image_jobs schema has already been ensured.
# _ensure_db runs the full migration DDL + several PRAGMA table_info probes on
# every create/get/list/transition, which dominates per-operation latency; the
# schema is immutable within a process lifetime once migrated, so re-probing on
# every call is pure waste. The SQL body is also read from disk only once.
_ENSURED_DBS: set[str] = set()
_MIGRATION_SQL: str | None = None

_MAX_PROVIDER_JSON_BYTES = 65_536
_MAX_ERROR_BYTES = 2_048
_MAX_TEXT_BYTES = 10_240


class ImageJobStatus(str, Enum):
    """Explicit lifecycle states for an image-generation job."""

    CREATED = "created"
    SUBMITTED = "submitted"
    RUNNING = "running"
    UNKNOWN = "unknown"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"

    def is_terminal(self) -> bool:
        return self in (ImageJobStatus.SUCCEEDED, ImageJobStatus.FAILED, ImageJobStatus.CANCELED)


# Allowed lifecycle transitions: {current: {next, ...}}
_ALLOWED_TRANSITIONS: dict[ImageJobStatus, set[ImageJobStatus]] = {
    ImageJobStatus.CREATED: {ImageJobStatus.SUBMITTED, ImageJobStatus.FAILED, ImageJobStatus.CANCELED},
    ImageJobStatus.SUBMITTED: {
        ImageJobStatus.RUNNING,
        ImageJobStatus.UNKNOWN,
        ImageJobStatus.FAILED,
        ImageJobStatus.CANCELED,
    },
    ImageJobStatus.RUNNING: {
        ImageJobStatus.UNKNOWN,
        ImageJobStatus.SUCCEEDED,
        ImageJobStatus.FAILED,
        ImageJobStatus.CANCELED,
    },
    ImageJobStatus.UNKNOWN: {ImageJobStatus.SUCCEEDED, ImageJobStatus.FAILED},
    ImageJobStatus.SUCCEEDED: set(),
    ImageJobStatus.FAILED: set(),
    ImageJobStatus.CANCELED: set(),
}


class ImageJobError(RuntimeError):
    """Raised when a job-store operation cannot complete safely."""


class JobNotFoundError(ImageJobError):
    """Raised when a job id does not exist."""


class IllegalTransitionError(ImageJobError):
    """Raised when a status transition is not permitted."""


@dataclass
class ImageJob:
    job_id: str
    provider: str
    provider_job_id: str | None
    operation: str
    status: ImageJobStatus
    prompt: str | None
    negative_prompt: str | None
    seed: int | None
    model_id: str | None
    preset_id: str | None
    width: int | None
    height: int | None
    steps: int | None
    guidance: float | None
    sampler: str | None
    scheduler: str | None
    provider_params_json: str | None
    workflow_template_id: str | None
    workflow_hash: str | None
    artifact_id: str | None
    canonical_artifact_id: str | None
    output_path: str | None
    normalized_error: str | None
    provider_diagnostics_json: str | None
    parent_id: str | None
    created_at: str
    updated_at: str
    started_at: str | None
    finished_at: str | None
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 0
    last_error: str | None = None
    queued_at: str | None = None
    #: FLUX.2 compiler provenance (IL-03/IL-04). NULL for legacy jobs.
    compiler_version: str | None = None
    compiler_params_json: str | None = None
    #: Immutable approved-plan provenance. NULL only for legacy/plan-less jobs.
    plan_id: str | None = None
    intent_json: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for fld in self.__dataclass_fields__:
            val = getattr(self, fld)
            if isinstance(val, Enum):
                val = val.value
            result[fld] = val
        return result


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_job_id() -> str:
    return f"job_{uuid.uuid4().hex}"


def _ensure_queue_columns(conn: Any) -> None:
    """Add queue columns if they don't exist (deferred migration)."""
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(image_jobs)").fetchall()}
    except Exception:
        cols = set()
    if "priority" not in cols:
        conn.execute("ALTER TABLE image_jobs ADD COLUMN priority INTEGER NOT NULL DEFAULT 0")
    if "retry_count" not in cols:
        conn.execute("ALTER TABLE image_jobs ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0")
    if "max_retries" not in cols:
        conn.execute("ALTER TABLE image_jobs ADD COLUMN max_retries INTEGER NOT NULL DEFAULT 0")
    if "last_error" not in cols:
        conn.execute("ALTER TABLE image_jobs ADD COLUMN last_error TEXT")
    if "queued_at" not in cols:
        conn.execute("ALTER TABLE image_jobs ADD COLUMN queued_at TEXT")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_image_jobs_queue ON image_jobs(priority DESC, created_at ASC)"
        " WHERE status IN ('created', 'submitted')"
    )


def _ensure_compiler_columns(conn: Any) -> None:
    """Add FLUX.2 compiler provenance columns if missing (deferred migration).

    IL-03/IL-04: every dispatched FLUX.2 job durably records its compiler
    version and the compiled request. Legacy jobs keep compiler_version NULL.
    """
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(image_jobs)").fetchall()}
    except Exception:
        cols = set()
    if "compiler_version" not in cols:
        conn.execute("ALTER TABLE image_jobs ADD COLUMN compiler_version TEXT")
    if "compiler_params_json" not in cols:
        conn.execute("ALTER TABLE image_jobs ADD COLUMN compiler_params_json TEXT")


def _ensure_plan_provenance_columns(conn: Any) -> None:
    """Add approved plan + ImageIntent provenance to image jobs."""
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(image_jobs)").fetchall()}
    except Exception:
        cols = set()
    if "plan_id" not in cols:
        conn.execute("ALTER TABLE image_jobs ADD COLUMN plan_id TEXT")
    if "intent_json" not in cols:
        conn.execute("ALTER TABLE image_jobs ADD COLUMN intent_json TEXT")


def _ensure_canonical_artifact_column(conn: Any) -> None:
    """Add the canonical Kitty Artifact link without changing legacy asset ids."""
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(image_jobs)").fetchall()}
    except Exception:
        cols = set()
    if "canonical_artifact_id" not in cols:
        conn.execute("ALTER TABLE image_jobs ADD COLUMN canonical_artifact_id TEXT")


def _ensure_db(conn: Any = None) -> None:
    """Apply only our migration so the store works on a fresh DB.

    If the table exists but has the old schema (id INTEGER, engine, kind,
    provider_status), drop and recreate it. This only fires during the
    IMG-01 transition period.
    """
    global _MIGRATION_SQL

    db_key = str(Path(_paths.KITTY_DB_FILE).resolve())
    if db_key in _ENSURED_DBS:
        return

    if _MIGRATION_SQL is None:
        _MIGRATION_SQL = _MIGRATION_FILE.read_text(encoding="utf-8")

    def _apply(c: Any) -> None:
        try:
            cols = {row[1] for row in c.execute("PRAGMA table_info(image_jobs)").fetchall()}
        except Exception:
            cols = set()
        if "engine" in cols:
            # Old schema from pre-port — drop and recreate with new schema.
            c.execute("DROP TABLE IF EXISTS image_jobs")
        c.executescript(_MIGRATION_SQL)

    if conn is not None:
        _apply(conn)
        _ensure_queue_columns(conn)
        _ensure_compiler_columns(conn)
        _ensure_plan_provenance_columns(conn)
        _ensure_canonical_artifact_column(conn)
    else:
        with kitty_db.connect(_paths.KITTY_DB_FILE) as c:
            _apply(c)
            _ensure_queue_columns(c)
            _ensure_compiler_columns(c)
            _ensure_plan_provenance_columns(c)
            _ensure_canonical_artifact_column(c)

    _ENSURED_DBS.add(db_key)


def _check_json_bounded(value: str | None, field_name: str) -> None:
    if value is None:
        return
    raw = value.encode("utf-8")
    if len(raw) > _MAX_PROVIDER_JSON_BYTES:
        raise ImageJobError(
            f"{field_name} exceeds {_MAX_PROVIDER_JSON_BYTES} bytes "
            f"({len(raw)} bytes supplied)"
        )
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ImageJobError(f"{field_name} is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ImageJobError(f"{field_name} must be a JSON object, got {type(parsed).__name__}")


def _check_text_bounded(value: str | None, field_name: str) -> None:
    if value is None:
        return
    raw = value.encode("utf-8")
    if len(raw) > _MAX_TEXT_BYTES:
        raise ImageJobError(
            f"{field_name} exceeds {_MAX_TEXT_BYTES} bytes "
            f"({len(raw)} bytes supplied)"
        )


def _check_error_bounded(value: str | None) -> None:
    if value is None:
        return
    raw = value.encode("utf-8")
    if len(raw) > _MAX_ERROR_BYTES:
        raise ImageJobError(
            f"normalized_error exceeds {_MAX_ERROR_BYTES} bytes "
            f"({len(raw)} bytes supplied)"
        )


def _row_to_job(row: Any) -> ImageJob:
    return ImageJob(
        job_id=row["job_id"],
        provider=row["provider"],
        provider_job_id=row["provider_job_id"],
        operation=row["operation"],
        status=ImageJobStatus(row["status"]),
        prompt=row["prompt"],
        negative_prompt=row["negative_prompt"],
        seed=row["seed"],
        model_id=row["model_id"],
        preset_id=row["preset_id"],
        width=row["width"],
        height=row["height"],
        steps=row["steps"],
        guidance=row["guidance"],
        sampler=row["sampler"],
        scheduler=row["scheduler"],
        provider_params_json=row["provider_params_json"],
        workflow_template_id=row["workflow_template_id"],
        workflow_hash=row["workflow_hash"],
        artifact_id=row["artifact_id"],
        canonical_artifact_id=row["canonical_artifact_id"],
        output_path=row["output_path"],
        normalized_error=row["normalized_error"],
        provider_diagnostics_json=row["provider_diagnostics_json"],
        parent_id=row["parent_id"],
        priority=row["priority"] if row["priority"] is not None else 0,
        retry_count=row["retry_count"] if row["retry_count"] is not None else 0,
        max_retries=row["max_retries"] if row["max_retries"] is not None else 0,
        last_error=row["last_error"],
        queued_at=row["queued_at"],
        compiler_version=row["compiler_version"],
        compiler_params_json=row["compiler_params_json"],
        plan_id=row["plan_id"],
        intent_json=row["intent_json"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )


def create_job(
    provider: str,
    operation: str,
    *,
    prompt: str | None = None,
    negative_prompt: str | None = None,
    seed: int | None = None,
    model_id: str | None = None,
    preset_id: str | None = None,
    width: int | None = None,
    height: int | None = None,
    steps: int | None = None,
    guidance: float | None = None,
    sampler: str | None = None,
    scheduler: str | None = None,
    provider_params_json: str | None = None,
    workflow_template_id: str | None = None,
    workflow_hash: str | None = None,
    provider_job_id: str | None = None,
    parent_id: str | None = None,
    priority: int = 0,
    max_retries: int = 0,
    compiler_version: str | None = None,
    compiler_params_json: str | None = None,
    plan_id: str | None = None,
    intent_json: str | None = None,
) -> ImageJob:
    """Create a new image-job record. Returns the job. Raises on validation failure."""
    _check_json_bounded(provider_params_json, "provider_params_json")
    _check_json_bounded(compiler_params_json, "compiler_params_json")
    _check_json_bounded(intent_json, "intent_json")
    _check_text_bounded(prompt, "prompt")
    _check_text_bounded(negative_prompt, "negative_prompt")
    if not provider or not provider.strip():
        raise ImageJobError("provider must not be empty")
    if not operation or not operation.strip():
        raise ImageJobError("operation must not be empty")
    if (plan_id is None) != (intent_json is None):
        raise ImageJobError("plan_id and intent_json must be provided together")
    if plan_id is not None:
        if not plan_id.strip():
            raise ImageJobError("plan_id must not be empty")
        _check_text_bounded(plan_id, "plan_id")
    valid_ops = {"txt2img", "img2img", "variation", "upscale", "inpaint"}
    if operation not in valid_ops:
        raise ImageJobError(
            f"operation must be one of {sorted(valid_ops)}, got {operation!r}"
        )

    job_id = _new_job_id()
    now = _now_iso()
    job = ImageJob(
        job_id=job_id,
        provider=provider.strip().lower(),
        provider_job_id=provider_job_id,
        operation=operation,
        status=ImageJobStatus.CREATED,
        prompt=prompt,
        negative_prompt=negative_prompt,
        seed=seed,
        model_id=model_id,
        preset_id=preset_id,
        width=width,
        height=height,
        steps=steps,
        guidance=guidance,
        sampler=sampler,
        scheduler=scheduler,
        provider_params_json=provider_params_json,
        workflow_template_id=workflow_template_id,
        workflow_hash=workflow_hash,
        artifact_id=None,
        canonical_artifact_id=None,
        output_path=None,
        normalized_error=None,
        provider_diagnostics_json=None,
        parent_id=parent_id,
        priority=priority,
        retry_count=0,
        max_retries=max_retries,
        last_error=None,
        queued_at=now if max_retries > 0 else None,
        compiler_version=compiler_version,
        compiler_params_json=compiler_params_json,
        plan_id=plan_id,
        intent_json=intent_json,
        created_at=now,
        updated_at=now,
        started_at=None,
        finished_at=None,
    )
    field_names = [f.name for f in dc_fields(job)]
    columns_sql = ", ".join(field_names)
    placeholders = ", ".join(["?"] * len(field_names))
    values = tuple(
        getattr(job, f).value if f == "status" else getattr(job, f)
        for f in field_names
    )
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        conn.execute(
            f"INSERT INTO image_jobs ({columns_sql}) VALUES ({placeholders})",
            values,
        )
    return job


def get_job(job_id: str) -> ImageJob | None:
    """Retrieve a job by its Kitty-owned job_id."""
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        row = conn.execute(
            "SELECT * FROM image_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
    return _row_to_job(row) if row else None


def find_by_provider(provider: str, provider_job_id: str) -> ImageJob | None:
    """Look up a job by provider + provider_job_id."""
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        row = conn.execute(
            "SELECT * FROM image_jobs WHERE provider = ? AND provider_job_id = ?",
            (provider, provider_job_id),
        ).fetchone()
    return _row_to_job(row) if row else None


def list_recent(
    limit: int = 50, *, statuses: set[ImageJobStatus] | frozenset[ImageJobStatus] | None = None
) -> list[ImageJob]:
    """Return the most recent jobs, optionally prefiltered by status."""
    if limit <= 0 or limit > 200:
        raise ImageJobError(f"limit must be between 1 and 200, got {limit}")
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        if statuses:
            values = sorted(status.value for status in statuses)
            placeholders = ",".join("?" for _ in values)
            rows = conn.execute(
                f"SELECT * FROM image_jobs WHERE status IN ({placeholders}) "
                "ORDER BY created_at DESC, job_id DESC LIMIT ?",
                (*values, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM image_jobs ORDER BY created_at DESC, job_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [_row_to_job(r) for r in rows]


def list_children(parent_id: str, limit: int = 200) -> list[ImageJob]:
    """Return variation/derivative jobs linked to ``parent_id``.

    Creation order is stable across restarts by ordering on the durable
    timestamp and UUID.  Rejecting an empty parent id avoids accidentally
    turning a lineage query into an unbounded gallery query.
    """
    if not parent_id or not parent_id.strip():
        raise ImageJobError("parent_id must not be empty")
    if limit <= 0 or limit > 200:
        raise ImageJobError(f"limit must be between 1 and 200, got {limit}")
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        rows = conn.execute(
            "SELECT * FROM image_jobs "
            "WHERE parent_id = ? ORDER BY created_at ASC, job_id ASC LIMIT ?",
            (parent_id, limit),
        ).fetchall()
    return [_row_to_job(r) for r in rows]


def transition(job_id: str, new_status: ImageJobStatus) -> ImageJob:
    """Transition a job's lifecycle state. Raises on illegal transition."""
    job = get_job(job_id)
    if job is None:
        raise JobNotFoundError(f"job {job_id} not found")

    current = job.status
    if new_status not in _ALLOWED_TRANSITIONS.get(current, set()):
        raise IllegalTransitionError(
            f"illegal transition: {current.value} -> {new_status.value} "
            f"for job {job_id}"
        )

    now = _now_iso()
    updates: dict[str, Any] = {
        "status": new_status.value,
        "updated_at": now,
    }
    if new_status == ImageJobStatus.SUCCEEDED:
        job_verify = get_job(job_id)
        if job_verify and not job_verify.artifact_id and not job_verify.output_path:
            raise ImageJobError(
                f"cannot mark job {job_id} succeeded: "
                "no artifact_id or output_path set"
            )
        updates["finished_at"] = now
    if new_status == ImageJobStatus.FAILED:
        updates["finished_at"] = now
    if new_status == ImageJobStatus.CANCELED:
        updates["finished_at"] = now
    if new_status == ImageJobStatus.RUNNING and current == ImageJobStatus.SUBMITTED:
        updates["started_at"] = now

    set_clauses = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [job_id]
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        conn.execute(
            f"UPDATE image_jobs SET {set_clauses} WHERE job_id = ?",
            values,
        )

    updated = get_job(job_id)
    assert updated is not None
    return updated


def update_job(
    job_id: str,
    *,
    provider_job_id: str | None = None,
    output_path: str | None = None,
    artifact_id: str | None = None,
    canonical_artifact_id: str | None = None,
    normalized_error: str | None = None,
    provider_diagnostics_json: str | None = None,
    started_at: str | None = None,
    workflow_hash: str | None = None,
    width: int | None = None,
    height: int | None = None,
) -> ImageJob:
    """Update mutable fields on an existing job. Fails loud on bad input."""
    job = get_job(job_id)
    if job is None:
        raise JobNotFoundError(f"job {job_id} not found")
    if job.status.is_terminal():
        raise ImageJobError(f"job {job_id} is terminal ({job.status.value}); cannot update")

    _check_error_bounded(normalized_error)
    _check_json_bounded(provider_diagnostics_json, "provider_diagnostics_json")
    for value, field in ((width, "width"), (height, "height")):
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
        ):
            raise ImageJobError(f"{field} must be a positive integer")

    cols: dict[str, Any] = {"updated_at": _now_iso()}
    if provider_job_id is not None:
        cols["provider_job_id"] = provider_job_id
    if output_path is not None:
        cols["output_path"] = output_path
    if artifact_id is not None:
        cols["artifact_id"] = artifact_id
    if canonical_artifact_id is not None:
        cols["canonical_artifact_id"] = canonical_artifact_id
    if normalized_error is not None:
        cols["normalized_error"] = normalized_error
    if provider_diagnostics_json is not None:
        cols["provider_diagnostics_json"] = provider_diagnostics_json
    if started_at is not None:
        cols["started_at"] = started_at
    if workflow_hash is not None:
        cols["workflow_hash"] = workflow_hash
    if width is not None:
        cols["width"] = width
    if height is not None:
        cols["height"] = height

    set_clauses = ", ".join(f"{k} = ?" for k in cols)
    values = list(cols.values()) + [job_id]
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        conn.execute(
            f"UPDATE image_jobs SET {set_clauses} WHERE job_id = ?",
            values,
        )

    updated = get_job(job_id)
    assert updated is not None
    return updated


def set_parent(job_id: str, parent_id: str) -> ImageJob:
    """Record lineage on an already-created job without touching its operation.

    Iteration re-runs an approved plan, which recreates the job with the same
    operation (txt2img/img2img). Lineage is bookkeeping, not a render input, so
    it is attached after the fact here rather than overloading ``parent_id`` on
    the creation path (where it doubles as the img2img/variation anchor).
    Unlike ``update_job`` this is allowed on terminal jobs, because a child's
    lineage is recorded after it has already succeeded.
    """
    job = get_job(job_id)
    if job is None:
        raise JobNotFoundError(f"job {job_id} not found")
    if not parent_id or not parent_id.strip():
        raise ImageJobError("parent_id must not be empty")
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        conn.execute(
            "UPDATE image_jobs SET parent_id = ?, updated_at = ? WHERE job_id = ?",
            (parent_id, _now_iso(), job_id),
        )
    updated = get_job(job_id)
    assert updated is not None
    if updated.canonical_artifact_id:
        from gateway import artifact_store

        existing_artifact = artifact_store.get_artifact(updated.canonical_artifact_id)
        project_id = existing_artifact.get("project_id") if existing_artifact else None
        register_canonical_artifact(job_id, project_id=project_id)
        updated = get_job(job_id)
        assert updated is not None
    return updated


def register_canonical_artifact(
    job_id: str, *, project_id: int | None = None
) -> dict[str, Any]:
    """Register a persisted image output in Kitty's canonical Artifact spine.

    The legacy ``artifact_id`` field may contain a provider/worker asset id and
    is intentionally left untouched. Registration is deterministic by job id so
    restart/retry repair cannot create duplicate Library entries. Artifact row
    creation and the image-job link share one SQLite transaction.
    """
    from gateway import artifact_store

    job = get_job(job_id)
    if job is None:
        raise JobNotFoundError(f"job {job_id} not found")
    if not job.output_path:
        raise ImageJobError(f"job {job_id} has no persisted output_path to register")
    path = Path(job.output_path)
    if not path.is_file():
        raise ImageJobError(f"job {job_id} output is missing from disk: {path}")
    if Path(artifact_store.ARTIFACTS_DB_FILE) != Path(_paths.KITTY_DB_FILE):
        raise ImageJobError(
            "image jobs and canonical Artifacts must share the same kitty.db"
        )

    parent_artifact_id = None
    if job.parent_id:
        parent = get_job(job.parent_id)
        if parent is not None:
            parent_artifact_id = parent.canonical_artifact_id

    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    artifact_store.init_db()
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        artifact = artifact_store.register_file(
            path,
            artifact_id=f"artifact_image_{job.job_id}",
            kind="image",
            media_type=media_type,
            project_id=project_id,
            created_by=f"image:{job.provider}",
            source_ref=job.job_id,
            metadata={
                "image_job_id": job.job_id,
                "provider": job.provider,
                "provider_job_id": job.provider_job_id,
                "provider_asset_id": job.artifact_id,
                "operation": job.operation,
                "model_id": job.model_id,
                "seed": job.seed,
                "width": job.width,
                "height": job.height,
                "compiler_version": job.compiler_version,
                "parent_job_id": job.parent_id,
                "parent_artifact_id": parent_artifact_id,
                "workflow_template_id": job.workflow_template_id,
                "workflow_hash": job.workflow_hash,
            },
            connection=conn,
            refresh_existing=True,
        )
        conn.execute(
            "UPDATE image_jobs SET canonical_artifact_id = ?, updated_at = ? "
            "WHERE job_id = ?",
            (artifact["id"], _now_iso(), job.job_id),
        )
    return artifact


# ── Provider-request normalization ──────────────────────────────────────────


def normalize_drawthings_request(
    *,
    prompt: str,
    negative_prompt: str | None = None,
    seed: int | None = None,
    width: int | None = None,
    height: int | None = None,
    steps: int | None = None,
    cfg_scale: float | None = None,
    sampler: str | None = None,
    denoising_strength: float | None = None,
    init_image: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Normalize a Draw Things / A1111-format generation request into core fields.

    Returns a dict with keys matching ``create_job()`` kwargs, plus
    ``provider_params_json`` for anything not in the core schema.
    """
    operation = "img2img" if init_image else "txt2img"
    extras: dict[str, Any] = dict(extra)
    if denoising_strength is not None:
        extras["denoising_strength"] = denoising_strength
    if init_image is not None:
        extras["init_image"] = init_image

    core: dict[str, Any] = {
        "provider": "drawthings",
        "operation": operation,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "seed": seed,
        "width": width,
        "height": height,
        "steps": steps,
        "guidance": cfg_scale,
        "sampler": sampler,
        "provider_params_json": json.dumps(extras, ensure_ascii=False) if extras else None,
    }
    return {k: v for k, v in core.items() if v is not None}


def normalize_comfyui_request(
    *,
    prompt: str,
    negative_prompt: str | None = None,
    seed: int | None = None,
    width: int | None = None,
    height: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
    sampler_name: str | None = None,
    scheduler: str | None = None,
    model_ckpt: str | None = None,
    workflow_template_id: str | None = None,
    workflow_hash: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Normalize a ComfyUI-format generation request into core fields.

    Returns a dict with keys matching ``create_job()`` kwargs. The
    ComfyUI-specific ``model_ckpt`` is placed into ``model_id``.
    """
    extras: dict[str, Any] = dict(extra)
    core: dict[str, Any] = {
        "provider": "comfyui",
        "operation": "txt2img",
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "seed": seed,
        "width": width,
        "height": height,
        "steps": steps,
        "guidance": cfg,
        "sampler": sampler_name,
        "scheduler": scheduler,
        "model_id": model_ckpt,
        "workflow_template_id": workflow_template_id,
        "workflow_hash": workflow_hash,
        "provider_params_json": json.dumps(extras, ensure_ascii=False) if extras else None,
    }
    return {k: v for k, v in core.items() if v is not None}


def reconcile_stale() -> int:
    """Reconcile image jobs orphaned by a gateway restart truthfully.

    A job that never left ``created`` is canceled because Kitty can prove no
    provider dispatch began. Once a job reached ``submitted`` or ``running``,
    the provider outcome is conservatively ``unknown`` regardless of whether
    Kitty managed to persist a provider receipt before the restart. This keeps
    accepted-but-response-lost submissions from being treated as safe retries.

    Returns the number of rows reconciled.
    """
    now = _now_iso()
    total = 0
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        cur = conn.execute(
            "UPDATE image_jobs SET status = ?, normalized_error = ?, "
            "updated_at = ?, finished_at = ? WHERE status = ?",
            (
                ImageJobStatus.CANCELED.value,
                "orphaned by gateway restart (never submitted to provider)",
                now,
                now,
                ImageJobStatus.CREATED.value,
            ),
        )
        total += cur.rowcount
        cur2 = conn.execute(
            "UPDATE image_jobs SET status = ?, normalized_error = ?, "
            "updated_at = ?, finished_at = NULL WHERE status IN (?, ?)",
            (
                ImageJobStatus.UNKNOWN.value,
                "gateway restarted; provider outcome unknown — reconciliation required",
                now,
                ImageJobStatus.SUBMITTED.value,
                ImageJobStatus.RUNNING.value,
            ),
        )
        total += cur2.rowcount
    return total


def list_queue(limit: int = 50) -> list[ImageJob]:
    """Return active dispatch jobs, excluding unresolved provider outcomes."""
    active = [
        ImageJobStatus.CREATED.value,
        ImageJobStatus.SUBMITTED.value,
        ImageJobStatus.RUNNING.value,
    ]
    if limit <= 0 or limit > 200:
        raise ImageJobError(f"limit must be between 1 and 200, got {limit}")
    placeholders = ",".join("?" for _ in active)
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        rows = conn.execute(
            f"SELECT * FROM image_jobs WHERE status IN ({placeholders}) "
            "ORDER BY priority DESC, created_at ASC LIMIT ?",
            (*active, limit),
        ).fetchall()
    return [_row_to_job(r) for r in rows]


def list_unknown(limit: int = 50) -> list[ImageJob]:
    """Return unresolved provider outcomes for recovery, oldest first."""
    if limit <= 0 or limit > 200:
        raise ImageJobError(f"limit must be between 1 and 200, got {limit}")
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        rows = conn.execute(
            "SELECT * FROM image_jobs WHERE status = ? "
            "ORDER BY updated_at ASC, job_id ASC LIMIT ?",
            (ImageJobStatus.UNKNOWN.value, limit),
        ).fetchall()
    return [_row_to_job(row) for row in rows]


def requeue(job_id: str) -> ImageJob:
    """Re-queue a failed job for retry. Increments retry_count and resets state.

    Raises:
        JobNotFoundError: job does not exist.
        ImageJobError: job is not in FAILED state, or retries exhausted.
    """
    job = get_job(job_id)
    if job is None:
        raise JobNotFoundError(f"job {job_id} not found")
    if job.status != ImageJobStatus.FAILED:
        raise ImageJobError(
            f"job {job_id} is {job.status.value}; only FAILED jobs can be requeued"
        )
    if job.retry_count >= job.max_retries:
        raise ImageJobError(
            f"job {job_id} has exhausted its {job.max_retries} retries"
        )

    now = _now_iso()
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        conn.execute(
            """UPDATE image_jobs SET
               status = ?, retry_count = retry_count + 1,
               normalized_error = NULL, last_error = normalized_error,
               provider_job_id = NULL, output_path = NULL,
               updated_at = ?, queued_at = ?,
               started_at = NULL, finished_at = NULL
               WHERE job_id = ?""",
            (ImageJobStatus.CREATED.value, now, now, job_id),
        )
        conn.commit()
    return get_job(job_id)  # type: ignore[return-value]


def retry_job(job_id: str) -> ImageJob:
    """Retry a failed job by minting a NEW child job with the same intent.

    Unlike ``requeue`` (which reuses the same row), a retry preserves lineage:
    the child records ``parent_id`` pointing at the original, and copies every
    generation parameter, provider/model metadata, compiler provenance, and the
    immutable plan + intent JSON verbatim. The new job gets a fresh job_id and
    attempt lifecycle. Privacy/content lane and character are preserved through
    the copied plan and intent, never re-derived from the request body.

    Only a FAILED job can be retried. A terminal job in any other state has no
    failed attempt to recover; duplicating a success is a separate operation.

    Raises:
        JobNotFoundError: job does not exist.
        ImageJobError: job is not in terminal FAILED state.
    """
    job = get_job(job_id)
    if job is None:
        raise JobNotFoundError(f"job {job_id} not found")
    if job.status != ImageJobStatus.FAILED:
        raise ImageJobError(
            f"job {job_id} is {job.status.value}; only terminal FAILED jobs can be retried"
        )
    return create_job(
        job.provider,
        job.operation,
        prompt=job.prompt,
        negative_prompt=job.negative_prompt,
        seed=job.seed,
        model_id=job.model_id,
        preset_id=job.preset_id,
        width=job.width,
        height=job.height,
        steps=job.steps,
        guidance=job.guidance,
        sampler=job.sampler,
        scheduler=job.scheduler,
        provider_params_json=job.provider_params_json,
        workflow_template_id=job.workflow_template_id,
        workflow_hash=job.workflow_hash,
        parent_id=job.job_id,
        priority=job.priority,
        max_retries=job.max_retries,
        compiler_version=job.compiler_version,
        compiler_params_json=job.compiler_params_json,
        plan_id=job.plan_id,
        intent_json=job.intent_json,
    )


def cancel_queued(character_id: str | None = None, provider: str | None = None) -> int:
    """Cancel locally active jobs without erasing unknown provider outcomes."""
    conditions = ["status IN ('created', 'submitted', 'running')"]
    params: list[Any] = []
    if character_id:
        conditions.append("character_id = ?")
        params.append(character_id)
    if provider:
        conditions.append("provider = ?")
        params.append(provider)

    now = _now_iso()
    where = " AND ".join(conditions)
    with kitty_db.connect(_paths.KITTY_DB_FILE) as conn:
        _ensure_db(conn)
        cur = conn.execute(
            f"UPDATE image_jobs SET status = ?, updated_at = ?, finished_at = ? "
            f"WHERE {where}",
            (ImageJobStatus.CANCELED.value, now, now, *params),
        )
        conn.commit()
    return cur.rowcount


__all__ = [
    "ImageJob",
    "ImageJobStatus",
    "ImageJobError",
    "JobNotFoundError",
    "IllegalTransitionError",
    "create_job",
    "get_job",
    "find_by_provider",
    "list_recent",
    "list_children",
    "list_queue",
    "list_unknown",
    "transition",
    "update_job",
    "set_parent",
    "requeue",
    "retry_job",
    "cancel_queued",
    "normalize_drawthings_request",
    "normalize_comfyui_request",
    "reconcile_stale",
]
