"""External source-image import for durable Image Lab img2img."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image
from starlette.datastructures import Headers

from gateway import artifact_store, image_jobs, image_sessions
from gateway.routes import image_studio_jobs


@pytest.fixture(autouse=True)
def _isolated_image_store(monkeypatch, tmp_path: Path):
    db_file = tmp_path / "kitty.db"
    data_dir = tmp_path / "data"
    monkeypatch.setattr(image_jobs._paths, "KITTY_DB_FILE", db_file)
    monkeypatch.setattr(image_sessions._paths, "KITTY_DB_FILE", db_file)
    monkeypatch.setattr(image_studio_jobs, "_SOURCE_IMAGE_ROOT", data_dir / "images" / "imports", raising=False)
    monkeypatch.setattr(artifact_store, "ARTIFACTS_DB_FILE", db_file)
    image_jobs._ENSURED_DBS.clear()
    yield
    image_jobs._ENSURED_DBS.clear()


def _png(size=(512, 512)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, format="PNG")
    return buffer.getvalue()


def _upload(data: bytes, *, name: str = "source.png", media_type: str = "image/png") -> UploadFile:
    return UploadFile(
        filename=name,
        file=io.BytesIO(data),
        headers=Headers({"content-type": media_type}),
    )


@pytest.mark.asyncio
async def test_imported_source_becomes_durable_job_artifact_and_anchor():
    session = image_sessions.create_session(title="external edit")

    result = await image_studio_jobs.studio_import_source_image(
        session.session_id, _upload(_png())
    )

    job = image_jobs.get_job(result["job"]["job_id"])
    assert job is not None
    assert job.provider == "upload"
    assert job.operation == "import"
    assert job.status is image_jobs.ImageJobStatus.SUCCEEDED
    assert job.width == 512 and job.height == 512
    assert Path(job.output_path).is_file()
    assert image_sessions.job_session_id(job.job_id) == session.session_id

    resumed = image_sessions.require_session(session.session_id)
    assert resumed.anchor_job_id == job.job_id
    assert resumed.anchor_artifact_id == job.canonical_artifact_id

    artifact = artifact_store.get_artifact(job.canonical_artifact_id)
    assert artifact is not None
    assert artifact["kind"] == "image"
    assert artifact["source_ref"] == job.job_id
    assert artifact["metadata"]["operation"] == "import"
    assert result["quality"]["dimensions"] == "512×512"


@pytest.mark.asyncio
async def test_import_rejects_corrupt_image_without_leaving_a_job():
    session = image_sessions.create_session()

    with pytest.raises(HTTPException) as exc:
        await image_studio_jobs.studio_import_source_image(
            session.session_id, _upload(b"not an image")
        )

    assert exc.value.status_code == 400
    assert image_jobs.list_recent() == []
    assert image_sessions.require_session(session.session_id).anchor_job_id is None


@pytest.mark.asyncio
async def test_import_rejects_non_image_media_type_before_persisting():
    session = image_sessions.create_session()

    with pytest.raises(HTTPException) as exc:
        await image_studio_jobs.studio_import_source_image(
            session.session_id, _upload(_png(), media_type="text/plain")
        )

    assert exc.value.status_code == 415
    assert image_jobs.list_recent() == []
