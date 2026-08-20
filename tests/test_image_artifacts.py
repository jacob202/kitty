"""Canonical Artifact registration for completed image jobs."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from gateway import artifact_store, image_jobs


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path: Path):
    db_file = tmp_path / "kitty.db"
    monkeypatch.setattr(image_jobs._paths, "KITTY_DB_FILE", db_file)
    monkeypatch.setattr(artifact_store, "ARTIFACTS_DB_FILE", db_file)
    return db_file


def _output(tmp_path: Path, name: str = "result.png") -> Path:
    path = tmp_path / name
    path.write_bytes(b"\x89PNG\r\n\x1a\nkitty-image")
    return path


def test_image_job_registers_one_canonical_artifact_without_overwriting_provider_asset(tmp_path):
    job = image_jobs.create_job(
        "kitty_worker", "img2img", prompt="edit", model_id="worker-model"
    )
    path = _output(tmp_path)
    image_jobs.update_job(job.job_id, output_path=str(path), artifact_id="worker_asset_123")

    first = image_jobs.register_canonical_artifact(job.job_id)
    second = image_jobs.register_canonical_artifact(job.job_id)

    assert first["id"] == second["id"]
    assert first["id"] == f"artifact_image_{job.job_id}"
    assert first["kind"] == "image"
    assert first["media_type"] == "image/png"
    assert first["source_ref"] == job.job_id
    assert first["metadata"]["image_job_id"] == job.job_id
    assert first["metadata"]["provider"] == "kitty_worker"
    assert first["metadata"]["operation"] == "img2img"
    assert first["metadata"]["model_id"] == "worker-model"
    assert image_jobs.get_job(job.job_id).artifact_id == "worker_asset_123"
    assert image_jobs.get_job(job.job_id).canonical_artifact_id == first["id"]
    assert len(artifact_store.list_artifacts(kind="image")) == 1


def test_image_artifact_preserves_parent_and_compiler_lineage(tmp_path):
    parent = image_jobs.create_job("flux2", "txt2img", model_id="flux-parent")
    parent_path = _output(tmp_path, "parent.png")
    image_jobs.update_job(parent.job_id, output_path=str(parent_path))
    parent_artifact = image_jobs.register_canonical_artifact(parent.job_id)

    child = image_jobs.create_job(
        "flux2",
        "img2img",
        parent_id=parent.job_id,
        model_id="flux-child",
        seed=42,
        width=1024,
        height=768,
        compiler_version="flux2@1",
        compiler_params_json='{"compiler_id":"flux2@1"}',
    )
    child_path = _output(tmp_path, "child.png")
    image_jobs.update_job(child.job_id, output_path=str(child_path))
    artifact = image_jobs.register_canonical_artifact(child.job_id)

    assert artifact["metadata"]["parent_job_id"] == parent.job_id
    assert artifact["metadata"]["parent_artifact_id"] == parent_artifact["id"]
    assert artifact["metadata"]["compiler_version"] == "flux2@1"
    assert artifact["metadata"]["seed"] == 42
    assert artifact["metadata"]["width"] == 1024
    assert artifact["metadata"]["height"] == 768
    assert artifact["project_id"] is None


def test_existing_image_job_schema_backfills_canonical_artifact_id_null(isolated_db):
    with sqlite3.connect(isolated_db) as conn:
        conn.execute("CREATE TABLE image_jobs (job_id TEXT PRIMARY KEY, provider TEXT, operation TEXT, status TEXT, created_at TEXT, updated_at TEXT)")
        conn.execute("INSERT INTO image_jobs VALUES ('job_old', 'flux2', 'txt2img', 'succeeded', 'now', 'now')")
        conn.commit()

    image_jobs._ensure_db()

    with sqlite3.connect(isolated_db) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(image_jobs)")}
        value = conn.execute("SELECT canonical_artifact_id FROM image_jobs WHERE job_id='job_old'").fetchone()[0]
    assert "canonical_artifact_id" in cols
    assert value is None

def test_artifact_and_job_link_roll_back_together_on_link_failure(tmp_path, isolated_db):
    job = image_jobs.create_job("flux2", "txt2img", model_id="flux-test")
    path = _output(tmp_path, "rollback.png")
    image_jobs.update_job(job.job_id, output_path=str(path))
    artifact_store.init_db()

    with sqlite3.connect(isolated_db) as conn:
        conn.execute(
            """
            CREATE TRIGGER reject_canonical_artifact_link
            BEFORE UPDATE OF canonical_artifact_id ON image_jobs
            BEGIN
                SELECT RAISE(ABORT, 'forced link failure');
            END
            """
        )
        conn.commit()

    with pytest.raises(sqlite3.IntegrityError, match="forced link failure"):
        image_jobs.register_canonical_artifact(job.job_id)

    assert artifact_store.list_artifacts(kind="image") == []
    assert image_jobs.get_job(job.job_id).canonical_artifact_id is None
