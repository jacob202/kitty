"""Tests for the durable image-job metadata store (IMG-01), repaired.

Tests cover the corrected contract: Kitty-owned job_id, proper lifecycle,
honest success semantics, exact seed capture, and provider normalization.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from gateway.image_jobs import (
    ArtifactNotFoundError,
    IllegalTransitionError,
    ImageJobStore,
    JobNotFoundError,
)


def _get(store: ImageJobStore, job_id: str) -> dict:
    job = store.get_job(job_id)
    assert job is not None, f"job {job_id!r} not found"
    return job


@pytest.fixture
def store(tmp_path: Path) -> ImageJobStore:
    return ImageJobStore(db_file=tmp_path / "test_kitty.db")


def _make_fake_png(path: Path) -> str:
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    return str(path)


# ── Identity ────────────────────────────────────────────────────────────────

def test_job_id_is_string_with_prefix(store: ImageJobStore) -> None:
    job_id = store.create_job(engine="drawthings", prompt="a cat")
    assert isinstance(job_id, str)
    assert job_id.startswith("job_")
    assert len(job_id) > 4


def test_job_id_unique_across_calls(store: ImageJobStore) -> None:
    ids = {store.create_job(engine="drawthings", prompt=f"p{i}") for i in range(20)}
    assert len(ids) == 20


def test_get_job_returns_correct_public_identity(store: ImageJobStore) -> None:
    job_id = store.create_job(engine="drawthings", prompt="a cat")
    job = _get(store, job_id)
    assert job["job_id"] == job_id


# ── Lifecycle ───────────────────────────────────────────────────────────────

def test_initial_status_is_created(store: ImageJobStore) -> None:
    job_id = store.create_job(engine="drawthings", prompt="a cat")
    assert _get(store, job_id)["provider_status"] == "created"


def test_submit_transition(store: ImageJobStore) -> None:
    job_id = store.create_job(engine="drawthings", prompt="a cat")
    store.submit_job(job_id, provider_job_id="p_001")
    job = _get(store, job_id)
    assert job["provider_status"] == "submitted"
    assert job["provider_job_id"] == "p_001"
    assert job["submitted_at"] is not None


def test_full_success_lifecycle(store: ImageJobStore, tmp_path: Path) -> None:
    out = _make_fake_png(tmp_path / "out.png")
    job_id = store.create_job(engine="drawthings", prompt="a cat", seed=42)
    store.submit_job(job_id, provider_job_id="p_001")
    store.complete_job(job_id, output_path=out)
    job = _get(store, job_id)
    assert job["provider_status"] == "succeeded"
    assert job["output_path"] == out
    assert job["output_verified"] == 1
    assert job["finished_at"] is not None
    assert job["completed_at"] is not None


def test_fail_lifecycle(store: ImageJobStore) -> None:
    job_id = store.create_job(engine="drawthings", prompt="a cat")
    store.submit_job(job_id, provider_job_id="p_001")
    store.fail_job(job_id, error_type="timeout", error_message="too slow")
    job = _get(store, job_id)
    assert job["provider_status"] == "failed"
    assert job["error_type"] == "timeout"
    assert job["error_message"] == "too slow"
    assert job["finished_at"] is not None


def test_cancel_after_fail(store: ImageJobStore) -> None:
    job_id = store.create_job(engine="drawthings", prompt="a cat")
    store.submit_job(job_id, provider_job_id="p_001")
    store.fail_job(job_id, error_type="timeout", error_message="too slow")
    store.cancel_job(job_id)
    assert _get(store, job_id)["provider_status"] == "canceled"


def test_cancel_requires_failed_first(store: ImageJobStore) -> None:
    job_id = store.create_job(engine="drawthings", prompt="a cat")
    with pytest.raises(IllegalTransitionError):
        store.cancel_job(job_id)


# ── Illegal transitions ─────────────────────────────────────────────────────

def test_created_to_succeeded_illegal(store: ImageJobStore, tmp_path: Path) -> None:
    job_id = store.create_job(engine="drawthings", prompt="x")
    out = _make_fake_png(tmp_path / "out.png")
    with pytest.raises(IllegalTransitionError):
        store.complete_job(job_id, output_path=out)


def test_succeeded_to_failed_illegal(store: ImageJobStore, tmp_path: Path) -> None:
    job_id = store.create_job(engine="drawthings", prompt="x")
    store.submit_job(job_id, provider_job_id="p1")
    out = _make_fake_png(tmp_path / "out.png")
    store.complete_job(job_id, output_path=out)
    with pytest.raises(IllegalTransitionError):
        store.fail_job(job_id, error_type="timeout", error_message="boom")


# ── Honest success ──────────────────────────────────────────────────────────

def test_complete_job_verifies_artifact_exists(store: ImageJobStore) -> None:
    job_id = store.create_job(engine="drawthings", prompt="x")
    store.submit_job(job_id, provider_job_id="p1")
    with pytest.raises(ArtifactNotFoundError):
        store.complete_job(job_id, output_path=str(Path("/nonexistent/out.png")))
    assert _get(store, job_id)["provider_status"] == "submitted"


def test_complete_job_sets_output_verified_one(store: ImageJobStore, tmp_path: Path) -> None:
    job_id = store.create_job(engine="drawthings", prompt="x")
    store.submit_job(job_id, provider_job_id="p1")
    out = _make_fake_png(tmp_path / "out.png")
    store.complete_job(job_id, output_path=out)
    assert _get(store, job_id)["output_verified"] == 1


# ── Seed capture ────────────────────────────────────────────────────────────

def test_seed_persisted_exactly(store: ImageJobStore) -> None:
    job_id = store.create_job(engine="drawthings", prompt="cat", seed=12345)
    assert _get(store, job_id)["seed"] == 12345


def test_seed_none_when_omitted(store: ImageJobStore) -> None:
    job_id = store.create_job(engine="drawthings", prompt="cat")
    assert _get(store, job_id)["seed"] is None


# ── Metadata normalization ──────────────────────────────────────────────────

def test_drawthings_metadata(store: ImageJobStore) -> None:
    job_id = store.create_job(
        engine="drawthings",
        prompt="sunset",
        negative_prompt="blurry",
        seed=42,
        model="sd_xl_base_1.0",
        width=512,
        height=512,
        steps=20,
        guidance=7.0,
        sampler="Euler a",
        scheduler="karras",
    )
    job = _get(store, job_id)
    assert job["negative_prompt"] == "blurry"
    assert job["seed"] == 42
    assert job["model"] == "sd_xl_base_1.0"
    assert job["width"] == 512
    assert job["height"] == 512
    assert job["steps"] == 20
    assert job["guidance"] == 7.0
    assert job["sampler"] == "Euler a"
    assert job["scheduler"] == "karras"


def test_comfyui_metadata(store: ImageJobStore) -> None:
    job_id = store.create_job(
        engine="comfyui",
        prompt="portrait",
        model="SD15_CKPT",
        sampler="euler_ancestral",
        scheduler="karras",
        provider_params={"lora_strength": 0.7, "explicit": True},
        workflow_template="sd15_basic",
    )
    job = _get(store, job_id)
    assert job["engine"] == "comfyui"
    assert job["model"] == "SD15_CKPT"
    assert job["sampler"] == "euler_ancestral"
    assert job["scheduler"] == "karras"
    assert job["workflow_template"] == "sd15_basic"
    assert json.loads(job["provider_params"]) == {"lora_strength": 0.7, "explicit": True}


# ── Provider params bounds ──────────────────────────────────────────────────

def test_provider_params_bounded(store: ImageJobStore) -> None:
    huge = {"data": "x" * 5000}
    with pytest.raises(ValueError):
        store.create_job(engine="drawthings", prompt="x", provider_params=huge)


# ── Validation ──────────────────────────────────────────────────────────────

def test_rejects_invalid_engine(store: ImageJobStore) -> None:
    with pytest.raises(ValueError):
        store.create_job(engine="bogus", prompt="x")


def test_rejects_invalid_kind(store: ImageJobStore) -> None:
    with pytest.raises(ValueError):
        store.create_job(engine="drawthings", prompt="x", kind="bogus")


def test_rejects_empty_prompt(store: ImageJobStore) -> None:
    with pytest.raises(ValueError):
        store.create_job(engine="drawthings", prompt="")


# ── Lookup ──────────────────────────────────────────────────────────────────

def test_missing_job_returns_none(store: ImageJobStore) -> None:
    assert store.get_job("job_nonexistent") is None


def test_missing_job_raises_on_transition(store: ImageJobStore) -> None:
    with pytest.raises(JobNotFoundError):
        store.submit_job("job_nonexistent", provider_job_id="x")


def test_find_by_provider(store: ImageJobStore) -> None:
    job_id = store.create_job(engine="drawthings", prompt="cat")
    store.submit_job(job_id, provider_job_id="p_abc")
    found = store.find_by_provider("p_abc")
    assert found is not None
    assert found["job_id"] == job_id


def test_find_by_provider_missing(store: ImageJobStore) -> None:
    assert store.find_by_provider("p_nonexistent") is None


# ── Persistence ─────────────────────────────────────────────────────────────

def test_persistence_across_store_instances(tmp_path: Path) -> None:
    db = tmp_path / "test_kitty.db"
    s1 = ImageJobStore(db_file=db)
    job_id = s1.create_job(engine="comfyui", prompt="a dog")
    s2 = ImageJobStore(db_file=db)
    job = s2.get_job(job_id)
    assert job is not None
    assert job["prompt"] == "a dog"
    assert job["job_id"] == job_id


def test_get_recent(store: ImageJobStore) -> None:
    for i in range(5):
        store.create_job(engine="drawthings", prompt=f"p{i}")
    recent = store.get_recent(limit=3)
    assert len(recent) == 3
    assert recent[0]["prompt"] == "p4"
    assert recent[-1]["prompt"] == "p2"


# ── Reconciliation stub ─────────────────────────────────────────────────────

def test_reconcile_stale_returns_zero(store: ImageJobStore) -> None:
    job_id = store.create_job(engine="drawthings", prompt="x")
    store.submit_job(job_id, provider_job_id="p1")
    assert store.reconcile_stale() == 0


# ── Timestamps ──────────────────────────────────────────────────────────────

def test_created_at_and_updated_at_set_on_create(store: ImageJobStore) -> None:
    job_id = store.create_job(engine="drawthings", prompt="cat")
    job = _get(store, job_id)
    assert job["created_at"] is not None
    assert job["updated_at"] == job["created_at"]


def test_updated_at_changes_on_transition(store: ImageJobStore) -> None:
    job_id = store.create_job(engine="drawthings", prompt="cat")
    created = _get(store, job_id)["updated_at"]
    store.submit_job(job_id, provider_job_id="p1")
    assert _get(store, job_id)["updated_at"] != created


# ── Migration from 023-shaped database ──────────────────────────────────────

def test_migration_023_to_024(tmp_path: Path) -> None:
    """Simulate a database created by the merged PR #208 (migration 023 only),
    then verify the repair migration adds job_id and backfills existing rows."""
    db = tmp_path / "legacy.db"
    raw = sqlite3.connect(db)
    raw.execute("PRAGMA foreign_keys = ON")
    raw.execute("PRAGMA journal_mode = WAL")
    mig = Path(__file__).resolve().parent.parent / "gateway" / "migrations"
    raw.executescript((mig / "023_image_jobs.sql").read_text(encoding="utf-8"))
    raw.execute(
        """INSERT INTO image_jobs (engine, prompt, provider_status, created_at)
           VALUES ('drawthings', 'legacy cat', 'pending', '2026-07-19T12:00:00')""",
    )
    old_id = raw.execute(
        "SELECT id FROM image_jobs ORDER BY id DESC LIMIT 1"
    ).fetchone()[0]
    raw.commit()
    raw.close()

    store = ImageJobStore(db_file=db)
    job = store.get_job(f"job_{old_id:020d}")
    assert job is None, "fallback-id lookup should not match"

    all_jobs = store.get_recent(limit=100)
    migrated = [j for j in all_jobs if j["prompt"] == "legacy cat"]
    assert len(migrated) == 1
    m = migrated[0]
    assert m["job_id"].startswith("job_")
    assert m["engine"] == "drawthings"
    assert m["prompt"] == "legacy cat"


# ── Normalized error field ──────────────────────────────────────────────────

def test_normalized_error_stored(store: ImageJobStore) -> None:
    job_id = store.create_job(engine="drawthings", prompt="cat")
    store.submit_job(job_id, provider_job_id="p1")
    store.fail_job(
        job_id,
        error_type="http_error",
        error_message="500",
        normalized_error="provider_internal_error",
    )
    assert _get(store, job_id)["normalized_error"] == "provider_internal_error"


def test_normalized_error_none_when_omitted(store: ImageJobStore) -> None:
    job_id = store.create_job(engine="drawthings", prompt="cat")
    store.submit_job(job_id, provider_job_id="p1")
    store.fail_job(job_id, error_type="http_error", error_message="500")
    assert _get(store, job_id)["normalized_error"] is None
