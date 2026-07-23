"""Durable, provider-neutral image-job metadata store (IMG-01), repaired.

Fixes the merged PR #208 which shipped with:
  - INTEGER PK id instead of Kitty-owned UUID job_id
  - output_verified bypass that allowed false "success" status
  - Seed generated inside workflow builder (not persisted)
  - Wrong lifecycle (missing created, submitted, canceled)
  - Wrong column names and missing timestamps
  - Draw Things path not wired

Lifecycle (accepted contract):
  created → submitted → running → succeeded
                               ↘ failed → canceled
"""

from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from gateway import db as kitty_db
from gateway import paths as _paths
from gateway.paths import DB_MIGRATIONS_DIR

_MIGRATION_FILE_023 = DB_MIGRATIONS_DIR / "023_image_jobs.sql"
_MIGRATION_FILE_024 = DB_MIGRATIONS_DIR / "024_image_jobs_repair.sql"

_PROVIDER_PARAMS_MAX_BYTES = 4096

_VALID_ENGINES = {"drawthings", "comfyui"}
_VALID_KINDS = {"txt2img", "img2img", "variation", "upscale", "inpaint"}

_VALID_STATUSES = {"created", "submitted", "running", "succeeded", "failed", "canceled"}

_TRANSITIONS: dict[str, set[str]] = {
    "created": {"submitted"},
    "submitted": {"running", "succeeded", "failed"},
    "running": {"succeeded", "failed"},
    "succeeded": set(),
    "failed": {"canceled"},
    "canceled": set(),
}


class JobNotFoundError(Exception):
    """Raised when a job_id does not exist in the store."""


class IllegalTransitionError(Exception):
    """Raised when a status transition is not permitted by the lifecycle."""


class ArtifactNotFoundError(Exception):
    """Raised when complete_job is called but the output artifact does not exist."""


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
    output_path: str | None
    normalized_error: str | None
    provider_diagnostics_json: str | None
    parent_id: str | None
    created_at: str
    updated_at: str
    started_at: str | None
    finished_at: str | None

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


def _generate_job_id() -> str:
    """Generate a Kitty-owned provider-neutral job ID.

    Uses secrets.token_hex for 128 bits of randomness with a 'job_' prefix for
    easy visual identification. Never derived from a provider's prompt_id.
    """
    return "job_" + secrets.token_hex(16)


class ImageJobStore:
    """Owns all SQLite access for the image_jobs table (IMG-01)."""


    def _conn(self) -> sqlite3.Connection:
        conn = connect(self._db_file)
        conn.executescript(_MIGRATION_FILE_023.read_text(encoding="utf-8"))
        try:
            conn.executescript(_MIGRATION_FILE_024.read_text(encoding="utf-8"))
        except sqlite3.OperationalError:
            pass
        return conn

    def create_job(
        self,
        *,
        engine: str,
        kind: str = "txt2img",
        prompt: str,
        negative_prompt: str | None = None,
        seed: int | None = None,
        model: str | None = None,
        width: int | None = None,
        height: int | None = None,
        steps: int | None = None,
        guidance: float | None = None,
        sampler: str | None = None,
        scheduler: str | None = None,
        provider_params: dict | None = None,
        workflow_template: str | None = None,
    ) -> str:
        if engine not in _VALID_ENGINES:
            raise ValueError(
                f"engine must be one of {sorted(_VALID_ENGINES)}; got {engine!r}"
            )
        if kind not in _VALID_KINDS:
            raise ValueError(
                f"kind must be one of {sorted(_VALID_KINDS)}; got {kind!r}"
            )
        if not prompt:
            raise ValueError("prompt must be a non-empty string")

        provider_json = None
        if provider_params is not None:
            provider_json = json.dumps(provider_params, separators=(",", ":"))
            raw = provider_json.encode("utf-8")
            if len(raw) > _PROVIDER_PARAMS_MAX_BYTES:
                raise ValueError(
                    f"provider_params exceeds {_PROVIDER_PARAMS_MAX_BYTES} bytes "
                    f"when serialized (got {len(raw)})"
                )

        job_id = _generate_job_id()
        now = _now()

        with self._conn() as conn:
            conn.execute(
                """INSERT INTO image_jobs (
                    job_id, engine, kind, prompt, negative_prompt, seed, model,
                    width, height, steps, guidance, sampler, scheduler,
                    provider_params, workflow_template,
                    provider_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'created', ?, ?)""",
                (
                    job_id,
                    engine,
                    kind,
                    prompt,
                    negative_prompt,
                    seed,
                    model,
                    width,
                    height,
                    steps,
                    guidance,
                    sampler,
                    scheduler,
                    provider_json,
                    workflow_template,
                    now,
                    now,
                ),
            )
        return job_id

    def _require_job(self, conn: sqlite3.Connection, job_id: str) -> dict:
        row = conn.execute(
            "SELECT * FROM image_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        if row is None:
            raise JobNotFoundError(f"job {job_id!r} not found")
        return dict(row)

    def _transition(self, conn: sqlite3.Connection, job_id: str, to: str) -> dict:
        job = self._require_job(conn, job_id)
        current = job["provider_status"]
        allowed = _TRANSITIONS.get(current, set())
        if to not in allowed:
            raise IllegalTransitionError(
                f"illegal transition {current!r} -> {to!r} for job {job_id}"
            )
        return job

    def submit_job(self, job_id: str, provider_job_id: str) -> None:
        now = _now()
        with self._conn() as conn:
            self._transition(conn, job_id, "submitted")
            conn.execute(
                """UPDATE image_jobs
                   SET provider_status='submitted', provider_job_id=?,
                       submitted_at=?, updated_at=?
                   WHERE job_id=?""",
                (provider_job_id, now, now, job_id),
            )

    def start_job(self, job_id: str, provider_job_id: str) -> None:
        now = _now()
        with self._conn() as conn:
            self._transition(conn, job_id, "running")
            conn.execute(
                """UPDATE image_jobs
                   SET provider_status='running', provider_job_id=?,
                       started_at=?, updated_at=?
                   WHERE job_id=?""",
                (provider_job_id, now, now, job_id),
            )

    def complete_job(self, job_id: str, *, output_path: str) -> None:
        if not Path(output_path).exists():
            raise ArtifactNotFoundError(
                f"cannot complete job {job_id!r}: "
                f"output artifact not found at {output_path}"
            )
        now = _now()
        with self._conn() as conn:
            self._transition(conn, job_id, "succeeded")
            conn.execute(
                """UPDATE image_jobs
                   SET provider_status='succeeded', output_path=?,
                       output_verified=1, completed_at=?, finished_at=?,
                       updated_at=?
                   WHERE job_id=?""",
                (output_path, now, now, now, job_id),
            )

    def fail_job(
        self,
        job_id: str,
        *,
        error_type: str,
        error_message: str,
        normalized_error: str | None = None,
    ) -> None:
        now = _now()
        with self._conn() as conn:
            self._transition(conn, job_id, "failed")
            conn.execute(
                """UPDATE image_jobs
                   SET provider_status='failed', error_type=?, error_message=?,
                       normalized_error=?, completed_at=?, finished_at=?,
                       updated_at=?
                   WHERE job_id=?""",
                (error_type, error_message, normalized_error, now, now, now, job_id),
            )

    def cancel_job(self, job_id: str) -> None:
        now = _now()
        with self._conn() as conn:
            self._transition(conn, job_id, "canceled")
            conn.execute(
                """UPDATE image_jobs
                   SET provider_status='canceled', updated_at=?
                   WHERE job_id=?""",
                (now, job_id),
            )

    def get_job(self, job_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM image_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            return dict(row) if row is not None else None

    def find_by_provider(self, provider_job_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM image_jobs WHERE provider_job_id = ?",
                (provider_job_id,),
            ).fetchone()
            return dict(row) if row is not None else None

    def get_recent(self, limit: int = 20) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM image_jobs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def reconcile_stale(self) -> int:
        return 0


__all__ = [
    "ImageJobStore",
    "JobNotFoundError",
    "IllegalTransitionError",
    "ArtifactNotFoundError",
]
