"""Tests for the durable image-job metadata store (IMG-01).

The store replaces gateway/image_gen.py's in-memory _history with a SQLite
table so jobs, seeds, and outputs survive restarts. These tests exercise the
public ImageJobStore API; the store is provider-neutral (Draw Things + ComfyUI
both record through it) and never stores an executable ComfyUI workflow graph.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from gateway.image_jobs import (
    IllegalTransitionError,
    ImageJobStore,
)


@pytest.fixture
def store(tmp_path: Path) -> ImageJobStore:
    return ImageJobStore(db_file=tmp_path / "test_kitty.db")


def test_create_and_retrieve(store: ImageJobStore) -> None:
    job_id = store.create_job(engine="drawthings", prompt="a cat")
    job = store.get_job(job_id)
    assert job is not None
    assert job["id"] == job_id
    assert job["engine"] == "drawthings"
    assert job["prompt"] == "a cat"
    assert job["provider_status"] == "pending"


def test_persistence_across_instances(tmp_path: Path) -> None:
    db = tmp_path / "test_kitty.db"
    s1 = ImageJobStore(db_file=db)
    job_id = s1.create_job(engine="comfyui", prompt="a dog")
    s2 = ImageJobStore(db_file=db)
    job = s2.get_job(job_id)
    assert job is not None
    assert job["prompt"] == "a dog"


def test_legal_transitions(store: ImageJobStore, tmp_path: Path) -> None:
    job_id = store.create_job(engine="drawthings", prompt="x")
    store.start_job(job_id, provider_job_id="abc123")
    job = store.get_job(job_id)
    assert job["provider_status"] == "running"
    assert job["provider_job_id"] == "abc123"
    assert job["started_at"] is not None

    out = tmp_path / "out.png"
    out.write_bytes(b"fake")
    store.complete_job(job_id, output_path=str(out))
    job = store.get_job(job_id)
    assert job["provider_status"] == "success"
    assert job["output_path"] == str(out)
    assert job["output_verified"] == 1
    assert job["completed_at"] is not None


def test_failed_transition(store: ImageJobStore) -> None:
    job_id = store.create_job(engine="drawthings", prompt="x")
    store.start_job(job_id, provider_job_id="p1")
    store.fail_job(job_id, error_type="timeout", error_message="boom")
    job = store.get_job(job_id)
    assert job["provider_status"] == "failed"
    assert job["error_type"] == "timeout"
    assert job["error_message"] == "boom"
    assert job["completed_at"] is not None


def test_illegal_transition_pending_to_success(store: ImageJobStore, tmp_path: Path) -> None:
    job_id = store.create_job(engine="drawthings", prompt="x")
    out = tmp_path / "out.png"
    out.write_bytes(b"fake")
    with pytest.raises(IllegalTransitionError):
        store.complete_job(job_id, output_path=str(out))


def test_illegal_transition_success_to_failed(store: ImageJobStore, tmp_path: Path) -> None:
    job_id = store.create_job(engine="drawthings", prompt="x")
    store.start_job(job_id, provider_job_id="p1")
    out = tmp_path / "out.png"
    out.write_bytes(b"fake")
    store.complete_job(job_id, output_path=str(out))
    with pytest.raises(IllegalTransitionError):
        store.fail_job(job_id, error_type="timeout", error_message="boom")


def test_drawthings_metadata_normalization(store: ImageJobStore) -> None:
    job_id = store.create_job(
        engine="drawthings",
        prompt="sunset",
        negative_prompt="blurry",
        seed=12345,
        model="sd_xl_base_1.0",
        width=512,
        height=512,
        steps=20,
        guidance=7.0,
        sampler="Euler a",
        scheduler="karras",
    )
    job = store.get_job(job_id)
    assert job["negative_prompt"] == "blurry"
    assert job["seed"] == 12345
    assert job["model"] == "sd_xl_base_1.0"
    assert job["width"] == 512
    assert job["height"] == 512
    assert job["steps"] == 20
    assert job["guidance"] == 7.0
    assert job["sampler"] == "Euler a"
    assert job["scheduler"] == "karras"


def test_comfyui_metadata_normalization(store: ImageJobStore) -> None:
    job_id = store.create_job(
        engine="comfyui",
        prompt="portrait",
        model="SD15_CKPT",
        sampler="euler_ancestral",
        scheduler="karras",
        provider_params={"lora_strength": 0.7, "explicit": True},
        workflow_template="sd15_basic",
    )
    job = store.get_job(job_id)
    assert job["engine"] == "comfyui"
    assert job["model"] == "SD15_CKPT"
    assert job["sampler"] == "euler_ancestral"
    assert job["scheduler"] == "karras"
    assert job["workflow_template"] == "sd15_basic"
    assert json.loads(job["provider_params"]) == {"lora_strength": 0.7, "explicit": True}


def test_provider_params_bounded(store: ImageJobStore) -> None:
    huge = {"data": "x" * 5000}
    with pytest.raises(ValueError):
        store.create_job(engine="drawthings", prompt="x", provider_params=huge)


def test_complete_job_verifies_artifact(store: ImageJobStore, tmp_path: Path) -> None:
    job_id = store.create_job(engine="drawthings", prompt="x")
    store.start_job(job_id, provider_job_id="p1")
    # Default verification: missing artifact -> fail loud, status unchanged.
    with pytest.raises(RuntimeError):
        store.complete_job(job_id, output_path=str(tmp_path / "missing.png"))
    assert store.get_job(job_id)["provider_status"] == "running"
    # Explicit output_verified=False: trust caller, transition to success.
    store.complete_job(job_id, output_path=str(tmp_path / "missing.png"), output_verified=False)
    job = store.get_job(job_id)
    assert job["provider_status"] == "success"
    assert job["output_verified"] == 0


def test_atomic_terminal_state(store: ImageJobStore, tmp_path: Path) -> None:
    job_id = store.create_job(engine="drawthings", prompt="x")
    store.start_job(job_id, provider_job_id="p1")
    out = tmp_path / "out.png"
    out.write_bytes(b"fake")
    store.complete_job(job_id, output_path=str(out))
    job = store.get_job(job_id)
    assert job["provider_status"] == "success"
    assert job["output_path"] == str(out)
    assert job["completed_at"] is not None


def test_failure_persistence(store: ImageJobStore) -> None:
    job_id = store.create_job(engine="drawthings", prompt="x")
    store.start_job(job_id, provider_job_id="p1")
    store.fail_job(job_id, error_type="http_error", error_message="500")
    job = store.get_job(job_id)
    assert job["provider_status"] == "failed"
    assert job["error_type"] == "http_error"
    assert job["error_message"] == "500"
    assert job["completed_at"] is not None


def test_malformed_metadata_rejection(store: ImageJobStore) -> None:
    with pytest.raises(ValueError):
        store.create_job(engine="bogus_engine", prompt="x")


def test_migration_from_existing_db(tmp_path: Path) -> None:
    db = tmp_path / "test_kitty.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE existing_table (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    s = ImageJobStore(db_file=db)
    job_id = s.create_job(engine="drawthings", prompt="x")
    assert s.get_job(job_id) is not None
    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='existing_table'"
    ).fetchall()
    assert len(rows) == 1


def test_concurrent_no_id_collision(store: ImageJobStore) -> None:
    ids = [store.create_job(engine="drawthings", prompt=f"p{i}") for i in range(10)]
    assert len(set(ids)) == 10


def test_get_recent(store: ImageJobStore) -> None:
    for i in range(5):
        store.create_job(engine="drawthings", prompt=f"p{i}")
    recent = store.get_recent(limit=3)
    assert len(recent) == 3
    assert recent[0]["prompt"] == "p4"
    assert recent[-1]["prompt"] == "p2"


def test_reconcile_stale_returns_zero(store: ImageJobStore) -> None:
    job_id = store.create_job(engine="drawthings", prompt="x")
    store.start_job(job_id, provider_job_id="p1")
    assert store.reconcile_stale() == 0


def test_missing_job_returns_none(store: ImageJobStore) -> None:
    assert store.get_job(99999) is None
