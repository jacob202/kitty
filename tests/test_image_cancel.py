"""IMG-02 contracts for cancellation safety, reconciliation, and race handling."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from gateway import image_gen
from gateway import image_jobs as jobs
from gateway.image_gen import (
    CancellationConflictError,
    CancellationUnsupportedError,
)
from gateway.image_jobs import (
    IllegalTransitionError,
    ImageJobStatus,
    JobNotFoundError,
)


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path: Path):
    import gateway.paths as paths

    original = paths.KITTY_DB_FILE
    paths.KITTY_DB_FILE = tmp_path / "kitty.db"
    yield
    paths.KITTY_DB_FILE = original


def _comfy_job(*, submitted: bool = True, provider_job_id: str = "prompt-abc"):
    job = jobs.create_job(provider="comfyui", operation="txt2img", prompt="a cat")
    if submitted:
        jobs.update_job(job.job_id, provider_job_id=provider_job_id)
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
    return job


def _drawthings_job():
    return jobs.create_job(provider="drawthings", operation="txt2img", prompt="a dog")


# ── Mock helpers for ComfyUI queue/history responses ────────────────────────


def _queue_response(running=None, pending=None):
    return {
        "queue_running": [[0, pid] for pid in (running or [])],
        "queue_pending": [[0, pid] for pid in (pending or [])],
    }


class _JsonResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class _MockClient:
    def __init__(self, queue_data=None, history_data=None, fail_on=None):
        self._queue_data = queue_data or _queue_response()
        self._history_data = history_data or {}
        self._fail_on = fail_on
        self.calls: list[tuple[str, str, dict | None]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def get(self, url, **_kwargs):
        self.calls.append(("GET", url, None))
        if self._fail_on == "queue" and "/queue" in url and "/history" not in url:
            raise Exception("ComfyUI queue API unreachable")
        if "/queue" in url and "/history" not in url:
            return _JsonResponse(self._queue_data)
        if "/history/" in url:
            return _JsonResponse(self._history_data)
        return _JsonResponse({})

    async def post(self, url, json=None, **_kwargs):
        self.calls.append(("POST", url, json))
        if self._fail_on == "interrupt" and "/interrupt" in url:
            raise Exception("interrupt failed")
        if self._fail_on == "queue_delete" and "/queue" in url:
            raise Exception("queue delete failed")
        return _JsonResponse({"ok": True})


# ── Core cancellation safety ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_running_prompt_interrupts_and_marks_canceled(monkeypatch):
    """When our prompt is the active ComfyUI prompt, /interrupt is sent."""
    job = _comfy_job(provider_job_id="prompt-run")
    client = _MockClient(queue_data=_queue_response(running=["prompt-run"]))
    monkeypatch.setattr(image_gen.httpx, "AsyncClient", lambda **_kw: client)

    result = await image_gen.cancel(job.job_id)

    assert result == {"canceled": True, "job_id": job.job_id, "status": "canceled"}
    assert jobs.get_job(job.job_id).status is ImageJobStatus.CANCELED
    assert any("/interrupt" in url for _, url, _ in client.calls)


@pytest.mark.asyncio
async def test_cancel_queued_prompt_deletes_from_queue(monkeypatch):
    """When our prompt is queued, it is removed via the queue DELETE API."""
    job = _comfy_job(provider_job_id="prompt-q")
    client = _MockClient(queue_data=_queue_response(pending=["prompt-q"]))
    monkeypatch.setattr(image_gen.httpx, "AsyncClient", lambda **_kw: client)

    result = await image_gen.cancel(job.job_id)

    assert result["canceled"] is True
    assert jobs.get_job(job.job_id).status is ImageJobStatus.CANCELED
    post_calls = [(url, data) for method, url, data in client.calls if method == "POST"]
    assert any(data == {"delete": ["prompt-q"]} for url, data in post_calls)
    assert not any("/interrupt" in url for url, _ in post_calls)


@pytest.mark.asyncio
async def test_cancel_rejects_different_running_prompt(monkeypatch):
    """When another prompt is running, our prompt is not interrupted."""
    job = _comfy_job(provider_job_id="prompt-mine")
    client = _MockClient(
        queue_data=_queue_response(running=["prompt-other"]),
        history_data={},
    )
    monkeypatch.setattr(image_gen.httpx, "AsyncClient", lambda **_kw: client)

    with pytest.raises(CancellationConflictError, match="not running, queued"):
        await image_gen.cancel(job.job_id)

    assert jobs.get_job(job.job_id).status is not ImageJobStatus.CANCELED


@pytest.mark.asyncio
async def test_cancel_rejects_completed_prompt(monkeypatch):
    """A prompt that already completed in ComfyUI cannot be canceled."""
    job = _comfy_job(provider_job_id="prompt-done")
    client = _MockClient(
        queue_data=_queue_response(),
        history_data={"prompt-done": {"outputs": {}}},
    )
    monkeypatch.setattr(image_gen.httpx, "AsyncClient", lambda **_kw: client)

    with pytest.raises(CancellationConflictError, match="already completed"):
        await image_gen.cancel(job.job_id)

    assert jobs.get_job(job.job_id).status is not ImageJobStatus.CANCELED


# ── Provider rejection ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_rejects_drawthings_job():
    """Draw Things jobs are rejected — no provider-specific cancel mechanism."""
    job = _drawthings_job()

    with pytest.raises(CancellationUnsupportedError, match="drawthings"):
        await image_gen.cancel(job.job_id)

    assert jobs.get_job(job.job_id).status is ImageJobStatus.CREATED


# ── Edge cases ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_unknown_job():
    with pytest.raises(JobNotFoundError):
        await image_gen.cancel("job_nonexistent")


@pytest.mark.asyncio
async def test_cancel_terminal_job():
    job = _comfy_job()
    jobs.transition(job.job_id, ImageJobStatus.CANCELED)

    with pytest.raises(IllegalTransitionError, match="already canceled"):
        await image_gen.cancel(job.job_id)


@pytest.mark.asyncio
async def test_cancel_missing_provider_job_id():
    """A job that was never submitted has no provider_job_id."""
    job = _comfy_job(submitted=False)

    with pytest.raises(CancellationConflictError, match="no provider_job_id"):
        await image_gen.cancel(job.job_id)

    assert jobs.get_job(job.job_id).status is ImageJobStatus.CREATED


# ── Multiple jobs / queue scenarios ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_with_multiple_running_and_queued(monkeypatch):
    """Our prompt is queued while another is running — delete from queue only."""
    job = _comfy_job(provider_job_id="prompt-ours")
    client = _MockClient(
        queue_data=_queue_response(running=["prompt-other"], pending=["prompt-ours", "prompt-third"]),
    )
    monkeypatch.setattr(image_gen.httpx, "AsyncClient", lambda **_kw: client)

    result = await image_gen.cancel(job.job_id)

    assert result["canceled"] is True
    post_calls = [(url, data) for method, url, data in client.calls if method == "POST"]
    assert any(data == {"delete": ["prompt-ours"]} for url, data in post_calls)
    assert not any("/interrupt" in url for url, _ in post_calls)


# ── Provider API failures ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_queue_api_failure_propagates(monkeypatch):
    """If ComfyUI's /queue endpoint is unreachable, the error propagates."""
    job = _comfy_job(provider_job_id="prompt-x")
    client = _MockClient(fail_on="queue")
    monkeypatch.setattr(image_gen.httpx, "AsyncClient", lambda **_kw: client)

    with pytest.raises(Exception, match="queue API unreachable"):
        await image_gen.cancel(job.job_id)

    assert jobs.get_job(job.job_id).status is not ImageJobStatus.CANCELED


@pytest.mark.asyncio
async def test_cancel_queue_delete_failure_leaves_state_unchanged(monkeypatch):
    """If the queue DELETE call fails, durable state must not change."""
    job = _comfy_job(provider_job_id="prompt-qf")
    client = _MockClient(
        queue_data=_queue_response(pending=["prompt-qf"]),
        fail_on="queue_delete",
    )
    monkeypatch.setattr(image_gen.httpx, "AsyncClient", lambda **_kw: client)

    with pytest.raises(Exception, match="queue delete failed"):
        await image_gen.cancel(job.job_id)

    assert jobs.get_job(job.job_id).status is ImageJobStatus.SUBMITTED


@pytest.mark.asyncio
async def test_cancel_interrupt_failure_leaves_state_unchanged(monkeypatch):
    """If /interrupt fails, durable state must not change."""
    job = _comfy_job(provider_job_id="prompt-if")
    client = _MockClient(
        queue_data=_queue_response(running=["prompt-if"]),
        fail_on="interrupt",
    )
    monkeypatch.setattr(image_gen.httpx, "AsyncClient", lambda **_kw: client)

    with pytest.raises(Exception, match="interrupt failed"):
        await image_gen.cancel(job.job_id)

    assert jobs.get_job(job.job_id).status is ImageJobStatus.SUBMITTED


# ── Cancellation racing completion ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_race_with_completion(monkeypatch):
    """If the job reaches SUCCEEDED before we call transition, cancel fails safely."""
    job = _comfy_job(provider_job_id="prompt-race")
    client = _MockClient(queue_data=_queue_response(running=["prompt-race"]))
    monkeypatch.setattr(image_gen.httpx, "AsyncClient", lambda **_kw: client)

    jobs.update_job(job.job_id, output_path="/tmp/done.png")
    jobs.transition(job.job_id, ImageJobStatus.RUNNING)
    jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)

    with pytest.raises(IllegalTransitionError, match="already succeeded"):
        await image_gen.cancel(job.job_id)


# ── Durable status correctness ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_durable_status_unchanged_on_provider_failure(monkeypatch):
    """Durable status changes only after the exact provider job is canceled."""
    job = _comfy_job(provider_job_id="prompt-dur")
    client = _MockClient(
        queue_data=_queue_response(),
        history_data={},
    )
    monkeypatch.setattr(image_gen.httpx, "AsyncClient", lambda **_kw: client)

    with pytest.raises(CancellationConflictError):
        await image_gen.cancel(job.job_id)

    current = jobs.get_job(job.job_id)
    assert current.status is ImageJobStatus.SUBMITTED


@pytest.mark.asyncio
async def test_durable_status_changes_only_after_provider_success(monkeypatch):
    """Durable status becomes canceled only after /interrupt or /queue delete succeeds."""
    job = _comfy_job(provider_job_id="prompt-ok")
    client = _MockClient(queue_data=_queue_response(running=["prompt-ok"]))
    monkeypatch.setattr(image_gen.httpx, "AsyncClient", lambda **_kw: client)

    result = await image_gen.cancel(job.job_id)

    assert result["status"] == "canceled"
    assert jobs.get_job(job.job_id).status is ImageJobStatus.CANCELED


# ── Route integration ──────────────────────────────────────────────────────


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

    async def unsupported(_job_id: str):
        raise CancellationUnsupportedError("drawthings not supported")

    monkeypatch.setattr(image_gen, "cancel", unsupported)
    with pytest.raises(HTTPException) as unsupported_error:
        await extended.image_cancel("job_dt")
    assert unsupported_error.value.status_code == 422

    async def conflict(_job_id: str):
        raise CancellationConflictError("prompt not found")

    monkeypatch.setattr(image_gen, "cancel", conflict)
    with pytest.raises(HTTPException) as conflict_error:
        await extended.image_cancel("job_conflict")
    assert conflict_error.value.status_code == 409


# ── Reconciliation ──────────────────────────────────────────────────────────


def test_reconcile_stale_distinguishes_submitted_from_unsubmitted():
    """Unsubmitted jobs are canceled; submitted jobs are failed (state unknown)."""
    never_submitted = jobs.create_job(provider="comfyui", operation="txt2img", prompt="a")
    submitted = _comfy_job(provider_job_id="prompt-sub")
    already_done = jobs.create_job(provider="comfyui", operation="txt2img", prompt="b")
    jobs.transition(already_done.job_id, ImageJobStatus.SUBMITTED)
    jobs.transition(already_done.job_id, ImageJobStatus.CANCELED)

    assert jobs.reconcile_stale() == 2

    ns = jobs.get_job(never_submitted.job_id)
    assert ns.status is ImageJobStatus.CANCELED
    assert "never submitted" in ns.normalized_error

    sub = jobs.get_job(submitted.job_id)
    assert sub.status is ImageJobStatus.FAILED
    assert "provider state unknown" in sub.normalized_error

    assert jobs.get_job(already_done.job_id).status is ImageJobStatus.CANCELED


def test_reconcile_stale_leaves_terminal_jobs_unchanged():
    succeeded = jobs.create_job(provider="comfyui", operation="txt2img", prompt="s")
    jobs.transition(succeeded.job_id, ImageJobStatus.SUBMITTED)
    jobs.update_job(succeeded.job_id, output_path="/done.png", provider_job_id="p1")
    jobs.transition(succeeded.job_id, ImageJobStatus.RUNNING)
    jobs.transition(succeeded.job_id, ImageJobStatus.SUCCEEDED)

    assert jobs.reconcile_stale() == 0
    assert jobs.get_job(succeeded.job_id).status is ImageJobStatus.SUCCEEDED


def test_gateway_startup_reconciliation_reports_the_count(monkeypatch, caplog):
    from gateway import app

    monkeypatch.setattr(jobs, "reconcile_stale", lambda: 2)

    app._reconcile_image_jobs_on_startup()

    assert "reconciled 2 orphaned image job(s)" in caplog.text


# ── Generate flow ───────────────────────────────────────────────────────────


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

    class _ViewResponse:
        content = b"png-bytes"

        def raise_for_status(self):
            return None

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url: str, json: dict):
            assert url == f"{image_gen.COMFY_URL}/prompt"
            assert json["prompt"]
            return _PromptResponse()

        async def get(self, url: str, **kwargs):
            if url == f"{image_gen.COMFY_URL}/history/prompt-123":
                return _HistoryResponse()
            assert url == f"{image_gen.COMFY_URL}/view"
            assert kwargs["params"] == {"filename": "cat.png", "subfolder": "", "type": "output"}
            return _ViewResponse()

    async def no_wait(_seconds: float) -> None:
        return None

    monkeypatch.setattr(image_gen.httpx, "AsyncClient", lambda **_kwargs: _Client())
    monkeypatch.setattr(image_gen.asyncio, "sleep", no_wait)
    monkeypatch.setattr(image_gen, "save_image", lambda data, prefix: Path("/tmp/kitty-test-image.png"))

    result = await image_gen.generate("a cat")

    assert result["prompt_id"] == "prompt-123"
    assert jobs.get_job(result["job_id"]).status is ImageJobStatus.SUCCEEDED
