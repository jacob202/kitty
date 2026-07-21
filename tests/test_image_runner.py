"""Tests for the image runner module — job lifecycle and engine dispatch."""
from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway import image_jobs
from gateway.image_jobs import ImageJobStatus
from gateway.image_runner import ImageRunnerError, JobResult, run


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    """Point the job store at a temp SQLite DB for isolation."""
    db_file = tmp_path / "kitty.db"
    monkeypatch.setattr("gateway.paths.KITTY_DB_FILE", db_file)
    monkeypatch.setattr("gateway.image_jobs._paths.KITTY_DB_FILE", db_file)
    from gateway import db as kitty_db
    kitty_db.migrate(db_file=db_file)
    return db_file


# ── Helpers ──────────────────────────────────────────────────────────────────


def _fake_drawthings_engine(available: bool = True, data: bytes = b"fakepng"):
    """Build a mock Draw Things engine."""
    engine = MagicMock()
    engine.model_name = "test-model"
    engine._adapter = MagicMock()
    engine._adapter.is_available = MagicMock(return_value=available)
    engine.generate_async = AsyncMock(return_value=data)
    return engine


# ── ComfyUI path (via image_gen.generate) ────────────────────────────────────


class TestComfyUIPath:
    @pytest.mark.asyncio
    async def test_success_returns_job_result(self, tmp_path):
        """Successful ComfyUI generation returns JobResult with terminal job."""
        with (
            patch("gateway.image_gen.is_available", new_callable=AsyncMock, return_value=True),
            patch("gateway.image_gen.generate", new_callable=AsyncMock) as mock_gen,
        ):
            mock_gen.return_value = {
                "prompt_id": "p1",
                "filename": str(tmp_path / "out.png"),
                "job_id": "job_test123",
            }
            result = await run("comfyui", "a landscape")

            assert isinstance(result, JobResult)
            assert result.engine == "comfyui"
            assert result.filename == str(tmp_path / "out.png")

    @pytest.mark.asyncio
    async def test_comfyui_not_running_raises(self):
        """When ComfyUI is down, raises ImageRunnerError."""
        with patch("gateway.image_gen.is_available", new_callable=AsyncMock, return_value=False):
            with pytest.raises(ImageRunnerError, match="not running"):
                await run("comfyui", "a landscape")

    @pytest.mark.asyncio
    async def test_recipe_recorded_on_result(self, tmp_path):
        """Recipe ID is passed through to JobResult."""
        recipe = MagicMock()
        recipe.recipe_id = "comfyui_sdxl_standard"

        with (
            patch("gateway.image_gen.is_available", new_callable=AsyncMock, return_value=True),
            patch("gateway.image_gen.generate", new_callable=AsyncMock) as mock_gen,
        ):
            mock_gen.return_value = {
                "prompt_id": "p1",
                "filename": str(tmp_path / "out.png"),
                "job_id": "job_test456",
            }
            result = await run("comfyui", "a portrait", recipe=recipe)
            assert result.recipe == "comfyui_sdxl_standard"


# ── Draw Things path ─────────────────────────────────────────────────────────


class TestDrawThingsPath:
    @pytest.mark.asyncio
    async def test_success_returns_job_result(self, tmp_path):
        """Successful Draw Things generation returns JobResult."""
        fake_engine = _fake_drawthings_engine(available=True, data=b"fakepng")

        with (
            patch("mcp.imagen.engines.get", return_value=fake_engine),
            patch("mcp.imagen.io.save_image", return_value=tmp_path / "dt_out.png"),
        ):
            result = await run("drawthings", "a bear")

            assert isinstance(result, JobResult)
            assert result.engine == "drawthings"
            assert result.job_id.startswith("job_")
            fake_engine.generate_async.assert_awaited_once_with("a bear")

    @pytest.mark.asyncio
    async def test_drawthings_not_running_raises(self):
        """When Draw Things is down, raises ImageRunnerError."""
        fake_engine = _fake_drawthings_engine(available=False)

        with patch("mcp.imagen.engines.get", return_value=fake_engine):
            with pytest.raises(ImageRunnerError, match="not running"):
                await run("drawthings", "a bear")

    @pytest.mark.asyncio
    async def test_engine_failure_marks_job_failed(self, tmp_path):
        """When the engine raises, the job reaches FAILED terminal state."""
        fake_engine = _fake_drawthings_engine(available=True)
        fake_engine.generate_async = AsyncMock(side_effect=RuntimeError("comfyui exploded"))

        with (
            patch("mcp.imagen.engines.get", return_value=fake_engine),
            pytest.raises(RuntimeError, match="exploded"),
        ):
            await run("drawthings", "a bear")

        # The job should be in FAILED state (invariant: terminal on exit)
        jobs = image_jobs.list_recent(limit=1)
        assert len(jobs) == 1
        assert jobs[0].status is ImageJobStatus.FAILED
        assert "exploded" in (jobs[0].normalized_error or "")

    @pytest.mark.asyncio
    async def test_recipe_workflow_template_id_recorded(self, tmp_path):
        """Recipe's workflow_template_id is recorded on the job."""
        recipe = MagicMock()
        recipe.recipe_id = "drawthings_standard"
        recipe.workflow_template_id = "dt_basic"

        fake_engine = _fake_drawthings_engine(available=True, data=b"fakepng")

        with (
            patch("mcp.imagen.engines.get", return_value=fake_engine),
            patch("mcp.imagen.io.save_image", return_value=tmp_path / "dt_out.png"),
        ):
            result = await run("drawthings", "a bear", recipe=recipe)

        jobs = image_jobs.list_recent(limit=1)
        assert len(jobs) == 1
        assert jobs[0].workflow_template_id == "dt_basic"


# ── Character path ───────────────────────────────────────────────────────────


class TestCharacterPath:
    @pytest.mark.asyncio
    async def test_character_no_refs_raises(self, tmp_path):
        """Character with no reference images raises ImageRunnerError."""
        mock_char = MagicMock()
        mock_char.name = "TestChar"

        with (
            patch("gateway.image_gen.is_available", new_callable=AsyncMock, return_value=True),
            patch("gateway.image_characters.get_character", return_value=mock_char),
            patch("gateway.image_characters.list_character_refs", return_value=[]),
            pytest.raises(ImageRunnerError, match="no reference images"),
        ):
            await run("comfyui", "draw my character", character_id="char_abc")

    @pytest.mark.asyncio
    async def test_character_success(self, tmp_path):
        """Character generation with a primary ref succeeds."""
        mock_char = MagicMock()
        mock_char.name = "TestChar"
        mock_ref = MagicMock()
        mock_ref.is_primary = True
        mock_ref.storage_path = str(tmp_path / "ref.png")

        with (
            patch("gateway.image_gen.is_available", new_callable=AsyncMock, return_value=True),
            patch("gateway.image_characters.get_character", return_value=mock_char),
            patch("gateway.image_characters.list_character_refs", return_value=[mock_ref]),
            patch("gateway.image_gen.generate_with_character", new_callable=AsyncMock) as mock_gen,
        ):
            mock_gen.return_value = {
                "prompt_id": "p_char",
                "filename": str(tmp_path / "char_out.png"),
                "job_id": "job_char123",
                "character_weight": 0.7,
            }
            result = await run("comfyui", "draw my character", character_id="char_abc")

            assert result.character_weight == 0.7
            assert result.engine == "comfyui"


# ── Validation ───────────────────────────────────────────────────────────────


class TestValidation:
    @pytest.mark.asyncio
    async def test_unknown_engine_raises(self):
        """Unknown engine name raises ImageRunnerError."""
        with pytest.raises(ImageRunnerError, match="unknown engine"):
            await run("midjourney", "a bear")

    @pytest.mark.asyncio
    async def test_invalid_engine_strips_whitespace(self):
        """Engine name is stripped and lowered."""
        with patch("gateway.image_gen.is_available", new_callable=AsyncMock, return_value=True):
            with patch("gateway.image_gen.generate", new_callable=AsyncMock) as mock_gen:
                mock_gen.return_value = {"prompt_id": "p", "filename": "f", "job_id": "j"}
                result = await run("  ComfyUI  ", "test")
                assert result.engine == "comfyui"
