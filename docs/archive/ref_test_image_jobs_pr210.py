"""IMG-01: durable provider-neutral image-job metadata store tests."""
from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

import pytest

from gateway import image_jobs as jobs
from gateway.image_jobs import ImageJobStatus

# ── Helpers ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path: Path):
    test_db = tmp_path / "kitty.db"
    test_db.parent.mkdir(parents=True, exist_ok=True)
    import gateway.paths as gp

    original = gp.KITTY_DB_FILE
    gp.KITTY_DB_FILE = test_db
    jobs._ensure_db()
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
        job = jobs.create_job(
            provider="drawthings",
            operation="txt2img",
            prompt="a dog",
            seed=42,
            width=512,
            height=512,
        )
        assert job.job_id.startswith("job_")
        assert job.provider == "drawthings"
        assert job.status == ImageJobStatus.CREATED

        retrieved = jobs.get_job(job.job_id)
        assert retrieved is not None
        assert retrieved.job_id == job.job_id
        assert retrieved.prompt == "a dog"
        assert retrieved.seed == 42
        assert retrieved.width == 512
        assert retrieved.height == 512

    def test_get_nonexistent_returns_none(self) -> None:
        assert jobs.get_job("job_nonexistent") is None


# ── 2. Persistence across a new store instance ─────────────────────────────


class TestNewInstance:
    def test_survives_new_instance(self, tmp_path: Path) -> None:
        test_db = tmp_path / "kitty.db"
        import gateway.paths as gp

        gp.KITTY_DB_FILE = test_db
        jobs._ensure_db()

        job1 = jobs.create_job(provider="comfyui", operation="txt2img", prompt="hello")

        # Simulate a new process: recreate the module-level connection.
        gp.KITTY_DB_FILE = test_db
        jobs._ensure_db()
        retrieved = jobs.get_job(job1.job_id)
        assert retrieved is not None
        assert retrieved.prompt == "hello"


# ── 3. Persistence across simulated process restart ────────────────────────


class TestProcessRestart:
    def test_survives_restart(self, tmp_path: Path) -> None:
        import gateway.paths as gp

        db_path = tmp_path / "restart_test.db"
        gp.KITTY_DB_FILE = db_path
        jobs._ensure_db()

        created = jobs.create_job(provider="comfyui", operation="txt2img", prompt="restart me")
        job_id = created.job_id

        # "Restart" — close all connections, recreate.
        gp.KITTY_DB_FILE = db_path
        jobs._ensure_db()
        retrieved = jobs.get_job(job_id)
        assert retrieved is not None
        assert retrieved.prompt == "restart me"
        assert retrieved.status == ImageJobStatus.CREATED


# ── 4. Kitty-owned job_id generation ───────────────────────────────────────


class TestJobId:
    def test_kitty_owned_id(self) -> None:
        job = _make_job()
        assert job.job_id.startswith("job_")
        # Verify it's a UUID under the prefix
        hex_part = job.job_id[len("job_"):]
        parsed = uuid.UUID(hex_part)
        assert parsed.version == 4

    def test_id_not_provider_dependent(self) -> None:
        dt = _make_job(provider="drawthings")
        cu = _make_job(provider="comfyui")
        assert dt.job_id != cu.job_id
        assert not dt.job_id.startswith("prompt_")
        assert not cu.job_id.startswith("prompt_")


# ── 5. Concurrent creation without ID collision ────────────────────────────


class TestConcurrentIds:
    def test_no_collision(self) -> None:
        ids = set()
        for _ in range(100):
            job = _make_job()
            assert job.job_id not in ids
            ids.add(job.job_id)
        assert len(ids) == 100


# ── 6. Lookup using provider plus provider_job_id ──────────────────────────


class TestFindByProvider:
    def test_find_by_provider(self) -> None:
        _make_job(provider="comfyui", provider_job_id="cu_abc123")
        found = jobs.find_by_provider("comfyui", "cu_abc123")
        assert found is not None
        assert found.provider_job_id == "cu_abc123"
        assert found.provider == "comfyui"

    def test_not_found_returns_none(self) -> None:
        assert jobs.find_by_provider("drawthings", "nonexistent") is None


# ── 7. Legal lifecycle transitions ─────────────────────────────────────────


class TestLegalTransitions:
    def test_created_to_submitted(self) -> None:
        job = _make_job()
        job = jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        assert job.status == ImageJobStatus.SUBMITTED

    def test_submitted_to_running(self) -> None:
        job = _make_job()
        job = jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        job = jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        assert job.status == ImageJobStatus.RUNNING
        assert job.started_at is not None

    def test_running_to_succeeded(self) -> None:
        job = _make_job()
        job = jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        job = jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        # Must have output_path or artifact_id for success
        jobs.update_job(job.job_id, output_path="/tmp/test.png")
        job = jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)
        assert job.status == ImageJobStatus.SUCCEEDED
        assert job.finished_at is not None

    def test_running_to_failed(self) -> None:
        job = _make_job()
        job = jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        job = jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        job = jobs.transition(job.job_id, ImageJobStatus.FAILED)
        assert job.status == ImageJobStatus.FAILED

    def test_created_to_canceled(self) -> None:
        job = _make_job()
        job = jobs.transition(job.job_id, ImageJobStatus.CANCELED)
        assert job.status == ImageJobStatus.CANCELED

    def test_full_lifecycle(self) -> None:
        job = _make_job()
        assert job.status == ImageJobStatus.CREATED
        job = jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        assert job.status == ImageJobStatus.SUBMITTED
        job = jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        assert job.status == ImageJobStatus.RUNNING
        jobs.update_job(job.job_id, output_path="/tmp/out.png")
        job = jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)
        assert job.status == ImageJobStatus.SUCCEEDED


# ── 8. Rejection of illegal lifecycle transitions ──────────────────────────


class TestIllegalTransitions:
    def test_created_to_succeeded(self) -> None:
        job = _make_job()
        with pytest.raises(jobs.ImageJobError, match="illegal transition"):
            jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)

    def test_submitted_to_created(self) -> None:
        job = _make_job()
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        with pytest.raises(jobs.ImageJobError, match="illegal transition"):
            jobs.transition(job.job_id, ImageJobStatus.CREATED)

    def test_running_to_created(self) -> None:
        job = _make_job()
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        with pytest.raises(jobs.ImageJobError, match="illegal transition"):
            jobs.transition(job.job_id, ImageJobStatus.CREATED)


# ── 9. Terminal-state immutability ─────────────────────────────────────────


class TestTerminalImmutability:
    def test_succeeded_is_terminal(self) -> None:
        job = _make_job()
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        jobs.update_job(job.job_id, output_path="/tmp/out.png")
        jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)
        with pytest.raises(jobs.ImageJobError, match="illegal transition"):
            jobs.transition(job.job_id, ImageJobStatus.FAILED)

    def test_failed_is_terminal(self) -> None:
        job = _make_job()
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        jobs.transition(job.job_id, ImageJobStatus.FAILED)
        with pytest.raises(jobs.ImageJobError, match="illegal transition"):
            jobs.transition(job.job_id, ImageJobStatus.RUNNING)

    def test_canceled_is_terminal(self) -> None:
        job = _make_job()
        jobs.transition(job.job_id, ImageJobStatus.CANCELED)
        with pytest.raises(jobs.ImageJobError, match="illegal transition"):
            jobs.transition(job.job_id, ImageJobStatus.CREATED)

    def test_terminal_update_rejected(self) -> None:
        job = _make_job()
        jobs.transition(job.job_id, ImageJobStatus.CANCELED)
        with pytest.raises(jobs.ImageJobError, match="terminal"):
            jobs.update_job(job.job_id, output_path="/tmp/out.png")


# ── 10. Success rejected when no output verification ───────────────────────


class TestSuccessRequiresOutput:
    def test_success_rejected_no_output(self) -> None:
        job = _make_job()
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        with pytest.raises(jobs.ImageJobError, match="no artifact_id or output_path"):
            jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)

    def test_success_accepted_with_artifact_id(self) -> None:
        job = _make_job()
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        jobs.update_job(job.job_id, artifact_id="artifact_abc")
        job = jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)
        assert job.status == ImageJobStatus.SUCCEEDED


# ── 11. Atomic terminal-state and metadata update ──────────────────────────


class TestAtomicTerminalState:
    def test_terminal_state_and_metadata_atomic(self, tmp_path: Path) -> None:
        import gateway.paths as gp

        db_path = tmp_path / "atomic_test.db"
        gp.KITTY_DB_FILE = db_path
        jobs._ensure_db()

        job = jobs.create_job(provider="comfyui", operation="txt2img", prompt="atomic")
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        jobs.update_job(job.job_id, output_path="/tmp/out.png")
        jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)

        gp.KITTY_DB_FILE = db_path
        jobs._ensure_db()
        retrieved = jobs.get_job(job.job_id)
        assert retrieved is not None
        assert retrieved.status == ImageJobStatus.SUCCEEDED
        assert retrieved.finished_at is not None
        assert retrieved.output_path == "/tmp/out.png"


# ── 12. Draw Things request normalization ──────────────────────────────────


class TestDrawThingsNormalization:
    def test_basic_txt2img(self) -> None:
        norm = jobs.normalize_drawthings_request(
            prompt="a cat",
            negative_prompt="dog",
            seed=1,
            width=512,
            height=512,
            steps=20,
            cfg_scale=7.0,
            sampler="euler_a",
        )
        assert norm["provider"] == "drawthings"
        assert norm["operation"] == "txt2img"
        assert norm["prompt"] == "a cat"
        assert norm["seed"] == 1

    def test_img2img_includes_init(self) -> None:
        norm = jobs.normalize_drawthings_request(
            prompt="edit this",
            init_image="/tmp/input.png",
            denoising_strength=0.6,
        )
        assert norm["operation"] == "img2img"
        params = json.loads(norm["provider_params_json"])
        assert params["init_image"] == "/tmp/input.png"
        assert params["denoising_strength"] == 0.6

    def test_provider_params_omitted_when_empty(self) -> None:
        norm = jobs.normalize_drawthings_request(prompt="hello")
        assert norm.get("provider_params_json") is None


# ── 13. ComfyUI request normalization ──────────────────────────────────────


class TestComfyuiNormalization:
    def test_basic_txt2img(self) -> None:
        norm = jobs.normalize_comfyui_request(
            prompt="a landscape",
            negative_prompt="ugly",
            seed=99,
            width=1024,
            height=1024,
            steps=6,
            cfg=1.5,
            sampler_name="euler",
            scheduler="sgm_uniform",
            model_ckpt="sd_xl.safetensors",
        )
        assert norm["provider"] == "comfyui"
        assert norm["operation"] == "txt2img"
        assert norm["model_id"] == "sd_xl.safetensors"
        assert norm["scheduler"] == "sgm_uniform"

    def test_with_workflow_metadata(self) -> None:
        norm = jobs.normalize_comfyui_request(
            prompt="test",
            workflow_template_id="wf_sd15_v2",
            workflow_hash="abc123",
        )
        assert norm["workflow_template_id"] == "wf_sd15_v2"
        assert norm["workflow_hash"] == "abc123"


# ── 14. Bounded provider_params_json ───────────────────────────────────────


class TestBoundedProviderParams:
    def test_within_limit(self) -> None:
        small = json.dumps({"lora": "test", "strength": 0.5})
        job = _make_job(provider_params_json=small)
        assert job.provider_params_json == small

    def test_exceeds_limit(self) -> None:
        big = {"x": "y" * 70_000}
        with pytest.raises(jobs.ImageJobError, match="provider_params_json exceeds"):
            _make_job(provider_params_json=json.dumps(big))


# ── 15. Rejection of malformed JSON ────────────────────────────────────────


class TestMalformedJson:
    def test_not_valid_json(self) -> None:
        with pytest.raises(jobs.ImageJobError, match="not valid JSON"):
            _make_job(provider_params_json="this is not json")

    def test_not_an_object(self) -> None:
        with pytest.raises(jobs.ImageJobError, match="must be a JSON object"):
            _make_job(provider_params_json='"just a string"')


# ── 16. Rejection of oversized provider metadata ───────────────────────────


class TestOversizedMetadata:
    def test_oversized_provider_params(self) -> None:
        huge = {"data": "x" * 70_000}
        with pytest.raises(jobs.ImageJobError, match="provider_params_json exceeds"):
            _make_job(provider_params_json=json.dumps(huge))

    def test_oversized_prompt(self) -> None:
        huge = "x" * 20_000
        with pytest.raises(jobs.ImageJobError, match="prompt exceeds"):
            _make_job(prompt=huge)


# ── 17. Failure and diagnostics persistence ────────────────────────────────


class TestFailureAndDiagnostics:
    def test_failure_and_diagnostics(self) -> None:
        job = _make_job()
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        jobs.update_job(
            job.job_id,
            normalized_error="CUDA out of memory",
            provider_diagnostics_json=json.dumps({"error_type": "memory", "code": "ENOMEM"}),
        )
        job = jobs.transition(job.job_id, ImageJobStatus.FAILED)
        assert job.normalized_error == "CUDA out of memory"
        assert job.status == ImageJobStatus.FAILED
        assert job.finished_at is not None
        assert job.provider_diagnostics_json is not None
        diag = json.loads(job.provider_diagnostics_json)
        assert diag["error_type"] == "memory"


# ── 18. Nullable output_path before success ────────────────────────────────


class TestNullableOutputPath:
    def test_output_path_nullable_on_create(self) -> None:
        job = _make_job()
        assert job.output_path is None

    def test_output_path_nullable_in_running(self) -> None:
        job = _make_job()
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        retrieved = jobs.get_job(job.job_id)
        assert retrieved is not None
        assert retrieved.output_path is None

    def test_output_path_nullable_on_failure(self) -> None:
        job = _make_job()
        jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        job = jobs.transition(job.job_id, ImageJobStatus.FAILED)
        assert job.output_path is None


# ── 19. Migration from existing Kitty database ─────────────────────────────


class TestMigration:
    def test_migration_adds_table(self, tmp_path: Path) -> None:
        import gateway.paths as gp
        from gateway import db as kitty_db

        db_path = tmp_path / "existing.db"
        gp.KITTY_DB_FILE = db_path

        # Apply foundation migration first (simulates an existing DB).
        kitty_db.migrate(db_file=db_path)

        # Now run image_jobs migration.
        jobs._ensure_db()

        # Verify the table exists and has the expected columns.
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(image_jobs)")}
        conn.close()
        assert "job_id" in cols
        assert "provider" in cols
        assert "status" in cols
        assert "created_at" in cols
        assert "output_path" in cols

    def test_migration_is_idempotent(self, tmp_path: Path) -> None:
        import gateway.paths as gp
        from gateway import db as kitty_db

        db_path = tmp_path / "existing2.db"
        gp.KITTY_DB_FILE = db_path
        kitty_db.migrate(db_file=db_path)
        applied2 = kitty_db.migrate(db_file=db_path)
        assert len(applied2) == 0
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        tables = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        conn.close()
        assert "image_jobs" in tables


# ── 20. Bounded recent-job history query ───────────────────────────────────


class TestRecentJobs:
    def test_list_recent_returns_newest_first(self) -> None:
        j1 = _make_job(prompt="first")
        j2 = _make_job(prompt="second")
        recent = jobs.list_recent(limit=10)
        assert len(recent) >= 2
        assert recent[0].job_id == j2.job_id
        assert recent[1].job_id == j1.job_id

    def test_list_recent_bounded(self) -> None:
        for i in range(5):
            _make_job(prompt=f"job_{i}")
        recent = jobs.list_recent(limit=3)
        assert len(recent) == 3

    def test_list_recent_rejects_bad_limit(self) -> None:
        with pytest.raises(jobs.ImageJobError):
            jobs.list_recent(limit=0)
        with pytest.raises(jobs.ImageJobError):
            jobs.list_recent(limit=300)


# ── 21. No regression to existing image-generation tests ───────────────────


class TestNoRegression:
    def test_existing_image_gen_importable(self) -> None:
        from gateway import image_gen  # noqa: F811

        assert image_gen is not None

    def test_existing_image_gen_history_preserved(self) -> None:
        from gateway import image_gen

        # The existing in-memory _history should still work.
        hist = image_gen.get_history()
        assert isinstance(hist, list)
