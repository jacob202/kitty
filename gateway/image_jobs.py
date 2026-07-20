"""Durable provider-neutral image-job metadata store.

Kitty-owned job_id is the primary key — never provider-dependent. Lifecycle
states and timestamps present from the start. Provider-specific metadata
isolated inside bounded JSON extension fields.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from gateway import db as kitty_db
from gateway.paths import KITTY_DB_FILE

_MAX_PROVIDER_JSON_BYTES = 65_536
_MAX_ERROR_BYTES = 2_048
_MAX_TEXT_BYTES = 10_240


class ImageJobStatus(str, Enum):
    """Explicit lifecycle states for an image-generation job."""

    CREATED = "created"
    SUBMITTED = "submitted"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"

    def is_terminal(self) -> bool:
        return self in (ImageJobStatus.SUCCEEDED, ImageJobStatus.FAILED, ImageJobStatus.CANCELED)


# Allowed lifecycle transitions: {current: {next, ...}}
_ALLOWED_TRANSITIONS: dict[ImageJobStatus, set[ImageJobStatus]] = {
    ImageJobStatus.CREATED: {ImageJobStatus.SUBMITTED, ImageJobStatus.FAILED, ImageJobStatus.CANCELED},
    ImageJobStatus.SUBMITTED: {ImageJobStatus.RUNNING, ImageJobStatus.FAILED, ImageJobStatus.CANCELED},
    ImageJobStatus.RUNNING: {ImageJobStatus.SUCCEEDED, ImageJobStatus.FAILED, ImageJobStatus.CANCELED},
    ImageJobStatus.SUCCEEDED: set(),
    ImageJobStatus.FAILED: set(),
    ImageJobStatus.CANCELED: set(),
}


class ImageJobError(RuntimeError):
    """Raised when a job-store operation cannot complete safely."""


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


def _new_job_id() -> str:
    return f"job_{uuid.uuid4().hex}"


def _ensure_db() -> None:
    kitty_db.migrate(db_file=KITTY_DB_FILE)


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
) -> ImageJob:
    """Create a new image-job record. Returns the job. Raises on validation failure."""
    _ensure_db()
    _check_json_bounded(provider_params_json, "provider_params_json")
    _check_text_bounded(prompt, "prompt")
    _check_text_bounded(negative_prompt, "negative_prompt")
    if not provider or not provider.strip():
        raise ImageJobError("provider must not be empty")
    if not operation or not operation.strip():
        raise ImageJobError("operation must not be empty")
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
        output_path=None,
        normalized_error=None,
        provider_diagnostics_json=None,
        parent_id=parent_id,
        created_at=now,
        updated_at=now,
        started_at=None,
        finished_at=None,
    )
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO image_jobs (
                job_id, provider, provider_job_id, operation, status,
                prompt, negative_prompt, seed, model_id, preset_id,
                width, height, steps, guidance, sampler, scheduler,
                provider_params_json, workflow_template_id, workflow_hash,
                artifact_id, output_path, normalized_error,
                provider_diagnostics_json, parent_id,
                created_at, updated_at, started_at, finished_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.job_id, job.provider, job.provider_job_id, job.operation,
                job.status.value, job.prompt, job.negative_prompt, job.seed,
                job.model_id, job.preset_id, job.width, job.height,
                job.steps, job.guidance, job.sampler, job.scheduler,
                job.provider_params_json, job.workflow_template_id,
                job.workflow_hash, job.artifact_id, job.output_path,
                job.normalized_error, job.provider_diagnostics_json,
                job.parent_id, job.created_at, job.updated_at,
                job.started_at, job.finished_at,
            ),
        )
        conn.commit()
    return job


def get_job(job_id: str) -> ImageJob | None:
    """Retrieve a job by its Kitty-owned job_id."""
    _ensure_db()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        row = conn.execute(
            "SELECT * FROM image_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
    return _row_to_job(row) if row else None


def find_by_provider(provider: str, provider_job_id: str) -> ImageJob | None:
    """Look up a job by provider + provider_job_id."""
    _ensure_db()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        row = conn.execute(
            "SELECT * FROM image_jobs WHERE provider = ? AND provider_job_id = ?",
            (provider, provider_job_id),
        ).fetchone()
    return _row_to_job(row) if row else None


def list_recent(limit: int = 50) -> list[ImageJob]:
    """Return the most recent jobs, newest first."""
    if limit <= 0 or limit > 200:
        raise ImageJobError(f"limit must be between 1 and 200, got {limit}")
    _ensure_db()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        rows = conn.execute(
            "SELECT * FROM image_jobs ORDER BY created_at DESC, job_id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_job(r) for r in rows]


def transition(job_id: str, new_status: ImageJobStatus) -> ImageJob:
    """Transition a job's lifecycle state. Raises on illegal transition.

    Terminal states are immutable. An explicit recovery mechanism
    (not yet implemented) may justify a later override.
    """
    job = get_job(job_id)
    if job is None:
        raise ImageJobError(f"job {job_id} not found")

    current = job.status
    if new_status not in _ALLOWED_TRANSITIONS.get(current, set()):
        raise ImageJobError(
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
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        conn.execute(
            f"UPDATE image_jobs SET {set_clauses} WHERE job_id = ?",
            values,
        )
        conn.commit()

    updated = get_job(job_id)
    assert updated is not None
    return updated


def update_job(
    job_id: str,
    *,
    provider_job_id: str | None = None,
    output_path: str | None = None,
    artifact_id: str | None = None,
    normalized_error: str | None = None,
    provider_diagnostics_json: str | None = None,
    started_at: str | None = None,
) -> ImageJob:
    """Update mutable fields on an existing job. Fails loud on bad input.

    Only callers that know what they are doing should set started_at directly;
    normally ``transition(…, RUNNING)`` sets it.
    """
    job = get_job(job_id)
    if job is None:
        raise ImageJobError(f"job {job_id} not found")
    if job.status.is_terminal():
        raise ImageJobError(f"job {job_id} is terminal ({job.status.value}); cannot update")

    _check_error_bounded(normalized_error)
    _check_json_bounded(provider_diagnostics_json, "provider_diagnostics_json")

    cols: dict[str, Any] = {"updated_at": _now_iso()}
    if provider_job_id is not None:
        cols["provider_job_id"] = provider_job_id
    if output_path is not None:
        cols["output_path"] = output_path
    if artifact_id is not None:
        cols["artifact_id"] = artifact_id
    if normalized_error is not None:
        cols["normalized_error"] = normalized_error
    if provider_diagnostics_json is not None:
        cols["provider_diagnostics_json"] = provider_diagnostics_json
    if started_at is not None:
        cols["started_at"] = started_at

    set_clauses = ", ".join(f"{k} = ?" for k in cols)
    values = list(cols.values()) + [job_id]
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        conn.execute(
            f"UPDATE image_jobs SET {set_clauses} WHERE job_id = ?",
            values,
        )
        conn.commit()

    updated = get_job(job_id)
    assert updated is not None
    return updated


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
        output_path=row["output_path"],
        normalized_error=row["normalized_error"],
        provider_diagnostics_json=row["provider_diagnostics_json"],
        parent_id=row["parent_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )


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

    Draw Things uses the A1111 REST schema. Provider-specific parameters
    (denoising_strength, init_image, etc.) are bundled into
    ``provider_params_json``.

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
    Other node-level knobs are bundled into ``provider_params_json``.
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
