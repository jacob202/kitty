"""Gateway dispatch of an approved edit (issue #336, slice A4b).

A3 could decide on an edit and A4 made the worker able to perform one, but
nothing joined them: ``image_runner`` always rendered text-to-image. These tests
pin the join — an img2img dispatch must carry the anchor's artifact to the
worker as ``source_image_id`` with an explicit ``denoise``.

No renderer runs here. The worker is a stub; what is under test is the request
the gateway builds, which is the thing issue #336 says a reroll cannot fake.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from gateway import image_jobs, image_plans, image_runner
from gateway import image_sessions as sessions
from gateway.image_runner import ImageRunnerError, run_edit
from gateway.runpod_worker import WorkerImage, WorkerJob, WorkerOutput

PNG = b"\x89PNG\r\n\x1a\n-fake-source-bytes"


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path: Path, monkeypatch):
    test_db = tmp_path / "kitty.db"
    test_db.parent.mkdir(parents=True, exist_ok=True)
    import gateway.paths as gp

    monkeypatch.setattr(gp, "KITTY_DB_FILE", test_db)
    monkeypatch.setattr(gp, "DATA_DIR", tmp_path / "data")

    conn = sqlite3.connect(str(test_db))
    conn.row_factory = sqlite3.Row
    image_plans._ensure_db(conn)
    conn.commit()
    conn.close()
    yield test_db


class StubWorker:
    """Records what the gateway asked the worker to render."""

    def __init__(self, *, outputs: list[WorkerOutput] | None = None):
        self.uploaded: bytes | None = None
        self.submitted: dict = {}
        self.downloaded: WorkerOutput | None = None
        self._outputs = outputs if outputs is not None else [
            WorkerOutput(
                asset_id="asset_1",
                filename="KittyWorker_00001_.png",
                media_type="image/png",
                size_bytes=12,
                sha256="a" * 64,
                download_url="/v1/jobs/w1/outputs/asset_1",
                width=1024,
                height=1024,
            )
        ]

    async def upload_source_image(self, data: bytes, **_kw) -> WorkerImage:
        self.uploaded = data
        return WorkerImage(
            image_id=f"{'e' * 64}.png",
            sha256="e" * 64,
            media_type="image/png",
            size_bytes=len(data),
            width=1024,
            height=1024,
        )

    async def submit(self, **kwargs) -> WorkerJob:
        self.submitted = kwargs
        return WorkerJob(
            job_id="w1",
            status="queued",
            workflow_sha256="f" * 64,
            prompt_id=None,
            submission_state="submitted",
            error=None,
            outputs=(),
        )

    async def wait(self, job_id: str, **_kw) -> WorkerJob:
        return WorkerJob(
            job_id=job_id,
            status="succeeded",
            workflow_sha256="f" * 64,
            prompt_id="p1",
            submission_state="submitted",
            error=None,
            outputs=tuple(self._outputs),
        )

    async def download(self, output: WorkerOutput) -> bytes:
        self.downloaded = output
        return b"edited-image-bytes"


def _succeeded_anchor(tmp_path: Path, *, prompt: str = "a portrait") -> str:
    job = image_jobs.create_job(provider="comfyui", operation="txt2img", prompt=prompt)
    image_jobs.transition(job.job_id, image_jobs.ImageJobStatus.SUBMITTED)
    image_jobs.transition(job.job_id, image_jobs.ImageJobStatus.RUNNING)
    artifact = tmp_path / f"{job.job_id}.png"
    artifact.write_bytes(PNG)
    image_jobs.update_job(
        job.job_id, output_path=str(artifact), artifact_id=f"art_{job.job_id}"
    )
    image_jobs.transition(job.job_id, image_jobs.ImageJobStatus.SUCCEEDED)
    return job.job_id


class TestEditDispatch:
    @pytest.mark.asyncio
    async def test_edit_sends_the_anchor_artifact_and_a_denoise(self, tmp_path: Path):
        """A4b's acceptance: the parent artifact reaches the worker as an input."""
        anchor = _succeeded_anchor(tmp_path)
        worker = StubWorker()

        result = await run_edit(
            "keep the face, broader build",
            anchor_job_id=anchor,
            worker=worker,
            denoise=0.45,
        )

        assert worker.uploaded == PNG
        assert worker.submitted["workflow_id"] == "image_to_image_v1"
        assert worker.submitted["source_image_id"] == f"{'e' * 64}.png"
        assert worker.submitted["denoise"] == 0.45
        assert result.engine == "kitty_worker"

    @pytest.mark.asyncio
    async def test_the_edit_job_records_its_parent_and_operation(self, tmp_path: Path):
        anchor = _succeeded_anchor(tmp_path)
        result = await run_edit(
            "broader build", anchor_job_id=anchor, worker=StubWorker()
        )

        job = image_jobs.get_job(result.job_id)
        assert job.operation == "img2img"
        assert job.parent_id == anchor
        assert job.workflow_template_id == "image_to_image_v1"
        assert json.loads(job.provider_params_json)["denoise"] == (
            image_runner.DEFAULT_EDIT_DENOISE
        )

    @pytest.mark.asyncio
    async def test_a_successful_edit_ends_terminal_with_a_verified_artifact(
        self, tmp_path: Path
    ):
        anchor = _succeeded_anchor(tmp_path)
        result = await run_edit(
            "broader build", anchor_job_id=anchor, worker=StubWorker()
        )

        job = image_jobs.get_job(result.job_id)
        assert job.status is image_jobs.ImageJobStatus.SUCCEEDED
        assert Path(job.output_path).read_bytes() == b"edited-image-bytes"
        assert job.artifact_id == "asset_1"

    @pytest.mark.asyncio
    async def test_the_edit_is_lineage_linked_to_the_anchor(self, tmp_path: Path):
        anchor = _succeeded_anchor(tmp_path)
        result = await run_edit(
            "broader build", anchor_job_id=anchor, worker=StubWorker()
        )
        children = image_jobs.list_children(anchor)
        assert [c.job_id for c in children] == [result.job_id]


class TestEditRefusals:
    @pytest.mark.asyncio
    async def test_unknown_anchor_is_refused_before_a_job_exists(self):
        worker = StubWorker()
        with pytest.raises(ImageRunnerError, match="no image job"):
            await run_edit("broader build", anchor_job_id="job_nope", worker=worker)
        assert worker.submitted == {}

    @pytest.mark.asyncio
    async def test_unfinished_anchor_is_refused(self):
        job = image_jobs.create_job(
            provider="comfyui", operation="txt2img", prompt="x"
        )
        with pytest.raises(ImageRunnerError, match="only a succeeded job"):
            await run_edit(
                "broader build", anchor_job_id=job.job_id, worker=StubWorker()
            )

    @pytest.mark.asyncio
    async def test_anchor_whose_artifact_vanished_is_refused(self, tmp_path: Path):
        anchor = _succeeded_anchor(tmp_path)
        Path(image_jobs.get_job(anchor).output_path).unlink()

        with pytest.raises(ImageRunnerError, match="missing from disk"):
            await run_edit(
                "broader build", anchor_job_id=anchor, worker=StubWorker()
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("denoise", [0, -0.1, 1.5])
    async def test_out_of_range_denoise_is_refused(self, tmp_path: Path, denoise: float):
        """denoise 0 returns the source untouched; that is not an edit."""
        anchor = _succeeded_anchor(tmp_path)
        with pytest.raises(ImageRunnerError, match="denoise must be within"):
            await run_edit(
                "broader build",
                anchor_job_id=anchor,
                worker=StubWorker(),
                denoise=denoise,
            )

    @pytest.mark.asyncio
    async def test_a_worker_success_with_no_artifact_fails_the_job(
        self, tmp_path: Path
    ):
        anchor = _succeeded_anchor(tmp_path)
        worker = StubWorker(outputs=[])

        with pytest.raises(ImageRunnerError, match="without an artifact"):
            await run_edit("broader build", anchor_job_id=anchor, worker=worker)

        edits = image_jobs.list_children(anchor)
        assert [e.status for e in edits] == [image_jobs.ImageJobStatus.FAILED]

    @pytest.mark.asyncio
    async def test_a_worker_failure_leaves_the_job_terminal(self, tmp_path: Path):
        anchor = _succeeded_anchor(tmp_path)

        class Failing(StubWorker):
            async def submit(self, **kwargs):
                raise RuntimeError("worker refused the job")

        with pytest.raises(RuntimeError, match="worker refused"):
            await run_edit("broader build", anchor_job_id=anchor, worker=Failing())

        edits = image_jobs.list_children(anchor)
        assert [e.status for e in edits] == [image_jobs.ImageJobStatus.FAILED]

    @pytest.mark.asyncio
    async def test_a_crafted_output_filename_cannot_escape_the_job_directory(
        self, tmp_path: Path
    ):
        anchor = _succeeded_anchor(tmp_path)
        worker = StubWorker(
            outputs=[
                WorkerOutput(
                    asset_id="asset_1",
                    filename="../../../../etc/pwned.png",
                    media_type="image/png",
                    size_bytes=12,
                    sha256="a" * 64,
                    download_url="/v1/jobs/w1/outputs/asset_1",
                    width=1024,
                    height=1024,
                )
            ]
        )

        result = await run_edit(
            "broader build", anchor_job_id=anchor, worker=worker
        )

        written = Path(image_jobs.get_job(result.job_id).output_path)
        assert written.name == "pwned.png"
        assert written.parent.name == result.job_id


class TestSessionIntegration:
    @pytest.mark.asyncio
    async def test_an_edit_can_run_from_a_session_anchor(self, tmp_path: Path):
        """The A3 → A4b join: what "use this" selected is what gets edited."""
        s = sessions.create_session(title="edit")
        anchor = _succeeded_anchor(tmp_path)
        sessions.attach_job(s.session_id, anchor)
        sessions.set_anchor(s.session_id, anchor)

        refreshed = sessions.require_session(s.session_id)
        worker = StubWorker()
        result = await run_edit(
            "keep the face, broader build",
            anchor_job_id=refreshed.anchor_job_id,
            worker=worker,
        )

        assert worker.submitted["source_image_id"].endswith(".png")
        assert image_jobs.get_job(result.job_id).parent_id == anchor
