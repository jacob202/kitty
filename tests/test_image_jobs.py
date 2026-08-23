"""Tests for the durable image-job metadata store (IMG-01).

Ported from PR #210's comprehensive test suite. Tests the module-level API:
create_job, get_job, find_by_provider, list_recent, transition, update_job,
and the normalization functions.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from gateway import image_jobs as jobs
from gateway.image_jobs import (
    IllegalTransitionError,
    ImageJobError,
    ImageJobStatus,
    JobNotFoundError,
)


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path: Path):
    test_db = tmp_path / "kitty.db"
    test_db.parent.mkdir(parents=True, exist_ok=True)
    import gateway.paths as gp

    original = gp.KITTY_DB_FILE
    gp.KITTY_DB_FILE = test_db

    conn = sqlite3.connect(str(test_db))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    jobs._ensure_db(conn)
    jobs._ensure_queue_columns(conn)
    conn.close()

    yield
    gp.KITTY_DB_FILE = original


def _make_job(**overrides: Any) -> jobs.ImageJob:
    kwargs: dict[str, Any] = dict(
        provider="comfyui",
        operation="txt2img",
        prompt="a cat",
    )
    kwargs.update(overrides)
    return jobs.create_job(**kwargs)


# ── 1. Create and retrieve ─────────────────────────────────────────────────


class TestCreateAndRetrieve:
    def test_create_and_retrieve(self) -> None:
        job = _make_job(provider="drawthings", prompt="a dog", seed=42)
        fetched = jobs.get_job(job.job_id)
        assert fetched is not None
        assert fetched.job_id == job.job_id
        assert fetched.provider == "drawthings"
        assert fetched.prompt == "a dog"
        assert fetched.seed == 42
        assert fetched.status == ImageJobStatus.CREATED

    def test_persistence_across_instances(self, tmp_path: Path) -> None:
        job = _make_job(prompt="persist me")
        fetched = jobs.get_job(job.job_id)
        assert fetched is not None
        assert fetched.prompt == "persist me"

    def test_job_id_is_uuid(self) -> None:
        job = _make_job()
        assert job.job_id.startswith("job_")
        assert len(job.job_id) == 36  # job_ + 32 hex chars

    def test_provider_normalized_lowercase(self) -> None:
        job = _make_job(provider="  DrawThings  ")
        assert job.provider == "drawthings"

    def test_created_and_updated_at_set(self) -> None:
        job = _make_job()
        assert job.created_at
        assert job.updated_at
        assert job.created_at == job.updated_at

    def test_empty_provider_raises(self) -> None:
        with pytest.raises(ImageJobError, match="provider must not be empty"):
            _make_job(provider="")

    def test_empty_operation_raises(self) -> None:
        with pytest.raises(ImageJobError, match="operation must not be empty"):
            _make_job(operation="")

    def test_invalid_operation_raises(self) -> None:
        with pytest.raises(ImageJobError, match="operation must be one of"):
            _make_job(operation="bogus")


# ── 2. Find by provider ────────────────────────────────────────────────────


class TestFindByProvider:
    def test_find_by_provider(self) -> None:
        job = _make_job(provider="comfyui")
        jobs.update_job(job.job_id, provider_job_id="prompt_abc123")
        found = jobs.find_by_provider("comfyui", "prompt_abc123")
        assert found is not None
        assert found.job_id == job.job_id

    def test_find_by_provider_not_found(self) -> None:
        assert jobs.find_by_provider("comfyui", "nope") is None


# ── 3. List recent ─────────────────────────────────────────────────────────


class TestListRecent:
    def test_list_recent(self) -> None:
        for i in range(5):
            _make_job(prompt=f"p{i}")
        recent = jobs.list_recent(limit=3)
        assert len(recent) == 3

    def test_list_recent_limit_bounded(self) -> None:
        with pytest.raises(ImageJobError, match="limit must be between"):
            jobs.list_recent(limit=0)
        with pytest.raises(ImageJobError, match="limit must be between"):
            jobs.list_recent(limit=300)


# ── 4. Lifecycle transitions ───────────────────────────────────────────────


class TestTransitions:
    def test_happy_path(self) -> None:
        job = _make_job()
        assert job.status == ImageJobStatus.CREATED

        job = jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        assert job.status == ImageJobStatus.SUBMITTED

        job = jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        assert job.status == ImageJobStatus.RUNNING
        assert job.started_at is not None

        jobs.update_job(job.job_id, output_path="/tmp/out.png")
        job = jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)
        assert job.status == ImageJobStatus.SUCCEEDED
        assert job.finished_at is not None

    def test_failed_path(self) -> None:
        job = _make_job()
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        job = jobs.transition(job.job_id, ImageJobStatus.FAILED)
        assert job.status == ImageJobStatus.FAILED
        assert job.finished_at is not None

    def test_canceled_path(self) -> None:
        job = _make_job()
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        job = jobs.transition(job.job_id, ImageJobStatus.CANCELED)
        assert job.status == ImageJobStatus.CANCELED
        assert job.finished_at is not None

    def test_illegal_transition(self) -> None:
        job = _make_job()
        with pytest.raises(IllegalTransitionError):
            jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)

    def test_terminal_immutable(self) -> None:
        job = _make_job()
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        jobs.update_job(job.job_id, output_path="/tmp/out.png")
        jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)
        with pytest.raises(IllegalTransitionError):
            jobs.transition(job.job_id, ImageJobStatus.FAILED)
        with pytest.raises(ImageJobError, match="terminal"):
            jobs.update_job(job.job_id, output_path="/tmp/other.png")

    def test_nonexistent_job_raises(self) -> None:
        with pytest.raises(JobNotFoundError):
            jobs.transition("job_nonexistent", ImageJobStatus.SUBMITTED)

    def test_succeed_requires_output(self) -> None:
        job = _make_job()
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        with pytest.raises(ImageJobError, match="no artifact_id or output_path"):
            jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)


# ── 5. Update job ──────────────────────────────────────────────────────────


class TestUpdateJob:
    def test_update_provider_job_id(self) -> None:
        job = _make_job()
        updated = jobs.update_job(job.job_id, provider_job_id="p123")
        assert updated.provider_job_id == "p123"
        assert updated.updated_at >= job.created_at

    def test_update_output_path(self) -> None:
        job = _make_job()
        updated = jobs.update_job(job.job_id, output_path="/tmp/out.png")
        assert updated.output_path == "/tmp/out.png"

    def test_update_terminal_rejected(self) -> None:
        job = _make_job()
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        jobs.update_job(job.job_id, output_path="/tmp/out.png")
        jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)
        with pytest.raises(ImageJobError, match="terminal"):
            jobs.update_job(job.job_id, output_path="/tmp/other.png")

    def test_update_nonexistent_raises(self) -> None:
        with pytest.raises(JobNotFoundError):
            jobs.update_job("job_nonexistent", output_path="/tmp/x.png")


# ── 6. Normalization functions ─────────────────────────────────────────────


class TestNormalization:
    def test_drawthings_txt2img(self) -> None:
        result = jobs.normalize_drawthings_request(
            prompt="sunset",
            negative_prompt="blurry",
            seed=42,
            cfg_scale=7.0,
        )
        assert result["provider"] == "drawthings"
        assert result["operation"] == "txt2img"
        assert result["seed"] == 42
        assert result["guidance"] == 7.0

    def test_drawthings_img2img(self) -> None:
        result = jobs.normalize_drawthings_request(
            prompt="edit",
            init_image="/tmp/input.png",
            denoising_strength=0.5,
        )
        assert result["operation"] == "img2img"
        params = json.loads(result["provider_params_json"])
        assert params["denoising_strength"] == 0.5
        assert params["init_image"] == "/tmp/input.png"

    def test_comfyui_txt2img(self) -> None:
        result = jobs.normalize_comfyui_request(
            prompt="portrait",
            cfg=1.5,
            sampler_name="euler",
            scheduler="sgm_uniform",
            model_ckpt="photonicFusionSDXL_final.safetensors",
            workflow_template_id="sdxl_photonic",
            workflow_hash="abc123",
        )
        assert result["provider"] == "comfyui"
        assert result["model_id"] == "photonicFusionSDXL_final.safetensors"
        assert result["workflow_hash"] == "abc123"

    def test_normalization_strips_none(self) -> None:
        result = jobs.normalize_comfyui_request(prompt="x")
        assert "seed" not in result
        assert "width" not in result


# ── 7. Bounds validation ───────────────────────────────────────────────────


class TestBounds:
    def test_provider_params_too_large(self) -> None:
        huge = json.dumps({"data": "x" * 70_000})
        with pytest.raises(ImageJobError, match="exceeds"):
            _make_job(provider_params_json=huge)

    def test_provider_params_invalid_json(self) -> None:
        with pytest.raises(ImageJobError, match="not valid JSON"):
            _make_job(provider_params_json="not json")

    def test_provider_params_not_object(self) -> None:
        with pytest.raises(ImageJobError, match="must be a JSON object"):
            _make_job(provider_params_json='["list"]')

    def test_error_bounded(self) -> None:
        job = _make_job()
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        with pytest.raises(ImageJobError, match="exceeds"):
            # Long error via update_job
            jobs.update_job(job.job_id, normalized_error="x" * 3000)


# ── 8. Reconcile stub ─────────────────────────────────────────────────────


class TestReconcile:
    def test_reconcile_stale_returns_zero(self) -> None:
        assert jobs.reconcile_stale() == 0

    def test_restart_marks_submitted_without_provider_receipt_unknown(self) -> None:
        job = _make_job()
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)

        assert jobs.reconcile_stale() == 1

        recovered = jobs.get_job(job.job_id)
        assert recovered is not None
        assert recovered.status == ImageJobStatus.UNKNOWN
        assert recovered.finished_at is None
        assert "provider outcome unknown" in (recovered.normalized_error or "")

    def test_restart_marks_running_with_provider_receipt_unknown(self) -> None:
        job = _make_job()
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.update_job(job.job_id, provider_job_id="provider-123")
        jobs.transition(job.job_id, ImageJobStatus.RUNNING)

        assert jobs.reconcile_stale() == 1

        recovered = jobs.get_job(job.job_id)
        assert recovered is not None
        assert recovered.status == ImageJobStatus.UNKNOWN
        assert recovered.provider_job_id == "provider-123"
        assert recovered.finished_at is None

    def test_unknown_provider_outcome_can_be_reconciled_to_success(self) -> None:
        job = _make_job()
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.reconcile_stale()
        jobs.update_job(job.job_id, output_path="/tmp/recovered.png")

        resolved = jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)

        assert resolved.status == ImageJobStatus.SUCCEEDED
        assert resolved.finished_at is not None

    def test_unknown_provider_outcome_can_be_reconciled_to_failure(self) -> None:
        job = _make_job()
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.reconcile_stale()

        resolved = jobs.transition(job.job_id, ImageJobStatus.FAILED)

        assert resolved.status == ImageJobStatus.FAILED
        assert resolved.finished_at is not None

    def test_unknown_restart_state_is_idempotent_and_not_requeued(self) -> None:
        job = _make_job(max_retries=2)
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.reconcile_stale()

        recovered = jobs.get_job(job.job_id)
        assert recovered is not None
        assert recovered.status == ImageJobStatus.UNKNOWN
        assert jobs.reconcile_stale() == 0
        with pytest.raises(ImageJobError, match="only FAILED jobs can be requeued"):
            jobs.requeue(job.job_id)


# ── 9. Integration with image_gen ──────────────────────────────────────────


class TestImageGenIntegration:
    def test_import_does_not_crash(self) -> None:
        import gateway.image_gen  # noqa: F401


# ── 10. Priority queue ────────────────────────────────────────────────────


class TestPriorityQueue:
    def test_create_with_priority(self) -> None:
        job = _make_job(priority=5)
        assert job.priority == 5

    def test_priority_defaults_to_zero(self) -> None:
        job = _make_job()
        assert job.priority == 0

    def test_list_queue_excludes_unknown_provider_outcomes(self) -> None:
        job = _make_job(priority=100)
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.reconcile_stale()

        assert job.job_id not in {queued.job_id for queued in jobs.list_queue(limit=10)}

    def test_list_queue_returns_non_terminal_ordered(self) -> None:
        _make_job(prompt="low", priority=0)
        _make_job(prompt="high", priority=10)
        queue = jobs.list_queue(limit=10)
        assert len(queue) >= 2
        # Highest priority first
        assert queue[0].priority >= queue[1].priority


# ── 11. Retry / requeue ───────────────────────────────────────────────────


class TestRetry:
    def test_create_with_max_retries(self) -> None:
        job = _make_job(max_retries=3)
        assert job.max_retries == 3
        assert job.retry_count == 0

    def test_requeue_failed_job(self) -> None:
        job = _make_job(max_retries=2)
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        jobs.transition(job.job_id, ImageJobStatus.FAILED)
        requeued = jobs.requeue(job.job_id)
        assert requeued.status == ImageJobStatus.CREATED
        assert requeued.retry_count == 1

    def test_requeue_not_failed_raises(self) -> None:
        job = _make_job(max_retries=2)
        with pytest.raises(ImageJobError, match="only FAILED jobs can be requeued"):
            jobs.requeue(job.job_id)

    def test_requeue_exhausted_raises(self) -> None:
        job = _make_job(max_retries=1)
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        jobs.transition(job.job_id, ImageJobStatus.FAILED)
        jobs.requeue(job.job_id)
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        jobs.transition(job.job_id, ImageJobStatus.FAILED)
        with pytest.raises(ImageJobError, match="exhausted"):
            jobs.requeue(job.job_id)

    def test_requeue_nonexistent_raises(self) -> None:
        with pytest.raises(JobNotFoundError):
            jobs.requeue("job_nonexistent")


# ── 12. Cancel queued ─────────────────────────────────────────────────────


class TestCancelQueued:
    def test_cancel_queued_preserves_unknown_provider_outcome(self) -> None:
        job = _make_job()
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.reconcile_stale()

        assert jobs.cancel_queued() == 0
        recovered = jobs.get_job(job.job_id)
        assert recovered is not None
        assert recovered.status == ImageJobStatus.UNKNOWN

    def test_cancel_queued_all(self) -> None:
        _make_job(prompt="a")
        _make_job(prompt="b")
        count = jobs.cancel_queued()
        assert count == 2

    def test_cancel_queued_by_provider(self) -> None:
        _make_job(provider="comfyui", prompt="c1")
        _make_job(provider="drawthings", prompt="d1")
        count = jobs.cancel_queued(provider="comfyui")
        assert count == 1
