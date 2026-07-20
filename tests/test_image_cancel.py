"""IMG-02 contracts for ComfyUI cancellation and restart reconciliation."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from gateway import image_gen
from gateway import image_jobs as jobs
from gateway.image_jobs import IllegalTransitionError, ImageJobStatus, JobNotFoundError


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path: Path):
    import gateway.paths as paths

    original = paths.KITTY_DB_FILE
    paths.KITTY_DB_FILE = tmp_path / "kitty.db"
    yield
    paths.KITTY_DB_FILE = original


def _running_job():
    job = jobs.create_job(provider="comfyui", operation="txt2img", prompt="a cat")
    jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
    return job


@pytest.mark.asyncio
async def test_cancel_interrupts_comfyui_and_marks_the_job_canceled(monkeypatch):
    job = _running_job()
    calls: list[str] = []

    class _Response:
        def raise_for_status(self) -> None:
            return None

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url: str):
            calls.append(url)
            return _Response()

    monkeypatch.setattr(image_gen.httpx, "AsyncClient", lambda **_kwargs: _Client())

    result = await image_gen.cancel(job.job_id)

    assert calls == [f"{image_gen.COMFY_URL}/interrupt"]
    assert result == {"canceled": True, "job_id": job.job_id, "status": "canceled"}
    assert jobs.get_job(job.job_id).status is ImageJobStatus.CANCELED


@pytest.mark.asyncio
async def test_cancel_rejects_unknown_and_terminal_jobs():
    with pytest.raises(JobNotFoundError):
        await image_gen.cancel("job_missing")

    job = _running_job()
    jobs.transition(job.job_id, ImageJobStatus.CANCELED)
    with pytest.raises(IllegalTransitionError, match="already canceled"):
        await image_gen.cancel(job.job_id)


@pytest.mark.asyncio
async def test_generate_marks_a_submitted_job_running_before_completion(monkeypatch):
    class _PromptResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"prompt_id": "prompt-123"}

    class _HistoryResponse:
        def json(self):
            return {"prompt-123": {"outputs": {"save": {"images": [{"filename": "cat.png"}]}}}}

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url: str, json: dict):
            assert url == f"{image_gen.COMFY_URL}/prompt"
            assert json["prompt"]
            return _PromptResponse()

        async def get(self, url: str):
            assert url == f"{image_gen.COMFY_URL}/history/prompt-123"
            return _HistoryResponse()

    async def no_wait(_seconds: float) -> None:
        return None

    monkeypatch.setattr(image_gen.httpx, "AsyncClient", lambda **_kwargs: _Client())
    monkeypatch.setattr(image_gen.asyncio, "sleep", no_wait)

    result = await image_gen.generate("a cat")

    assert result["prompt_id"] == "prompt-123"
    assert jobs.get_job(result["job_id"]).status is ImageJobStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_cancel_route_maps_known_job_failures(monkeypatch):
    from gateway.routes import extended

    async def missing(_job_id: str):
        raise JobNotFoundError("not found")

    monkeypatch.setattr(image_gen, "cancel", missing)
    with pytest.raises(HTTPException) as missing_error:
        await extended.image_cancel("job_missing")
    assert missing_error.value.status_code == 404

    async def terminal(_job_id: str):
        raise IllegalTransitionError("already canceled")

    monkeypatch.setattr(image_gen, "cancel", terminal)
    with pytest.raises(HTTPException) as terminal_error:
        await extended.image_cancel("job_terminal")
    assert terminal_error.value.status_code == 409


def test_reconcile_stale_marks_nonterminal_jobs_canceled():
    created = jobs.create_job(provider="comfyui", operation="txt2img", prompt="created")
    submitted = _running_job()
    completed = jobs.create_job(provider="comfyui", operation="txt2img", prompt="done")
    jobs.transition(completed.job_id, ImageJobStatus.SUBMITTED)
    jobs.transition(completed.job_id, ImageJobStatus.CANCELED)

    assert jobs.reconcile_stale() == 2

    for job_id in (created.job_id, submitted.job_id):
        reconciled = jobs.get_job(job_id)
        assert reconciled is not None
        assert reconciled.status is ImageJobStatus.CANCELED
        assert reconciled.normalized_error == "orphaned by gateway restart"
    assert jobs.get_job(completed.job_id).status is ImageJobStatus.CANCELED


def test_gateway_startup_reconciliation_reports_the_count(monkeypatch, caplog):
    from gateway import app

    monkeypatch.setattr(jobs, "reconcile_stale", lambda: 2)

    app._reconcile_image_jobs_on_startup()

    assert "reconciled 2 orphaned image job(s)" in caplog.text
