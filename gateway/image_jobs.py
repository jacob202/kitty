"""Durable, provider-neutral image-job metadata store (IMG-01).

Kitty's legacy Image Lab (gateway/image_gen.py) kept only an in-memory list of
recent jobs, so seeds and outputs were lost on restart. This store persists
every job in Kitty's SQLite database with a normalized, provider-neutral schema
so later packets (cancellation, atomic persistence, lineage, convergence) can
build on it.

Design boundaries:
- API-only to ComfyUI (GPL-3.0): we never store the executable workflow graph,
  only a template name/hash for reproducibility.
- provider_params is a bounded JSON blob (<= 4KB) for backend-specific extras.
- All status transitions are validated and applied in a single transaction.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from gateway.db import connect
from gateway.paths import DB_MIGRATIONS_DIR, KITTY_DB_FILE

_MIGRATION_FILE = DB_MIGRATIONS_DIR / "023_image_jobs.sql"

_PROVIDER_PARAMS_MAX_BYTES = 4096
_VALID_ENGINES = {"drawthings", "comfyui"}
_VALID_KINDS = {"txt2img", "img2img", "variation", "upscale", "inpaint"}
_VALID_STATUSES = {"pending", "running", "success", "failed"}

# Legal status transitions. Terminal states have no outgoing edges.
_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"running"},
    "running": {"success", "failed"},
    "success": set(),
    "failed": set(),
}


class JobNotFoundError(Exception):
    """Raised when a job id does not exist."""


class IllegalTransitionError(Exception):
    """Raised when a status transition is not permitted."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ImageJobStore:
    """Owns all SQLite access for the image_jobs table."""

    def __init__(self, db_file: Path = KITTY_DB_FILE) -> None:
        self._db_file = Path(db_file)

    def _conn(self) -> sqlite3.Connection:
        conn = connect(self._db_file)
        # Self-contained: ensure only our table exists so the store works on a
        # fresh DB without running the full (ALTER-based) migration chain.
        conn.executescript(_MIGRATION_FILE.read_text(encoding="utf-8"))
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
    ) -> int:
        if engine not in _VALID_ENGINES:
            raise ValueError(f"engine must be one of {sorted(_VALID_ENGINES)}; got {engine!r}")
        if kind not in _VALID_KINDS:
            raise ValueError(f"kind must be one of {sorted(_VALID_KINDS)}; got {kind!r}")
        if not prompt:
            raise ValueError("prompt must be a non-empty string")
        provider_json = None
        if provider_params is not None:
            provider_json = json.dumps(provider_params, separators=(",", ":"))
            if len(provider_json.encode("utf-8")) > _PROVIDER_PARAMS_MAX_BYTES:
                raise ValueError(
                    f"provider_params exceeds {_PROVIDER_PARAMS_MAX_BYTES} bytes when serialized"
                )

        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO image_jobs (
                    engine, kind, prompt, negative_prompt, seed, model,
                    width, height, steps, guidance, sampler, scheduler,
                    provider_params, workflow_template, provider_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (
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
                    _now(),
                ),
            )
            return int(cur.lastrowid)

    def _require_job(self, conn: sqlite3.Connection, job_id: int) -> dict:
        row = conn.execute("SELECT * FROM image_jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise JobNotFoundError(f"job {job_id} not found")
        return dict(row)

    def _transition(self, conn: sqlite3.Connection, job_id: int, to: str) -> None:
        job = self._require_job(conn, job_id)
        current = job["provider_status"]
        allowed = _TRANSITIONS.get(current, set())
        if to not in allowed:
            raise IllegalTransitionError(
                f"illegal transition {current!r} -> {to!r} for job {job_id}"
            )

    def start_job(self, job_id: int, provider_job_id: str) -> None:
        with self._conn() as conn:
            self._transition(conn, job_id, "running")
            conn.execute(
                "UPDATE image_jobs SET provider_status='running', provider_job_id=?, started_at=? WHERE id=?",
                (provider_job_id, _now(), job_id),
            )

    def complete_job(
        self,
        job_id: int,
        *,
        output_path: str,
        output_verified: bool = True,
    ) -> None:
        if output_verified and not Path(output_path).exists():
            raise RuntimeError(
                f"cannot mark job {job_id} success: artifact missing at {output_path}"
            )
        with self._conn() as conn:
            self._transition(conn, job_id, "success")
            conn.execute(
                "UPDATE image_jobs SET provider_status='success', output_path=?, output_verified=?, completed_at=? WHERE id=?",
                (output_path, 1 if output_verified else 0, _now(), job_id),
            )

    def fail_job(self, job_id: int, *, error_type: str, error_message: str) -> None:
        with self._conn() as conn:
            self._transition(conn, job_id, "failed")
            conn.execute(
                "UPDATE image_jobs SET provider_status='failed', error_type=?, error_message=?, completed_at=? WHERE id=?",
                (error_type, error_message, _now(), job_id),
            )

    def get_job(self, job_id: int) -> dict | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM image_jobs WHERE id = ?", (job_id,)).fetchone()
            return dict(row) if row is not None else None

    def get_recent(self, limit: int = 20) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM image_jobs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def reconcile_stale(self) -> int:
        """Flip orphaned running jobs to failed. Stub for IMG-02 (returns 0)."""
        return 0


__all__ = ["ImageJobStore", "JobNotFoundError", "IllegalTransitionError"]
