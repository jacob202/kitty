"""Tests for the image runner module — job lifecycle and engine dispatch."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway import image_jobs
from gateway.image_jobs import ImageJobStatus
from gateway.image_runner import ImageRunnerError, JobResult, run


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "kitty.db"
    monkeypatch.setattr("gateway.paths.KITTY_DB_FILE", db_file)
    monkeypatch.setattr("gateway.image_jobs._paths.KITTY_DB_FILE", db_file)
    monkeypatch.setattr("gateway.artifact_store.ARTIFACTS_DB_FILE", db_file)
    from gateway import db as kitty_db

    kitty_db.migrate(db_file=db_file)
    return db_file


def _save_image_to(path):
    def _save(data: bytes, **_kwargs):
        path.write_bytes(data)
        return path

    return _save


def _fake_drawthings_engine(available: bool = True, data: bytes = b"fakepng"):
    engine = MagicMock()
    engine.model_name = "test-model"
    engine._adapter = MagicMock()
    engine._adapter.is_available = MagicMock(return_value=available)
    engine.generate_async = AsyncMock(return_value=data)
    return engine


class TestComfyUIPath:
    @pytest.mark.asyncio
    async def test_success_returns_job_result(self, tmp_path):
        with (
            patch(
                "gateway.image_gen.is_available",
                new_callable=AsyncMock,
                return_value=True,
            ),
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
        with patch(
            "gateway.image_gen.is_available",
            new_callable=AsyncMock,
            return_value=False,
        ):
            with pytest.raises(ImageRunnerError, match="not running"):
                await run("comfyui", "a landscape")

    @pytest.mark.asyncio
    async def test_recipe_recorded_on_result(self, tmp_path):
        recipe = MagicMock()
        recipe.recipe_id = "comfyui_sdxl_standard"

        with (
            patch(
                "gateway.image_gen.is_available",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("gateway.image_gen.generate", new_callable=AsyncMock) as mock_gen,
        ):
            mock_gen.return_value = {
                "prompt_id": "p1",
                "filename": str(tmp_path / "out.png"),
                "job_id": "job_test456",
            }
            result = await run("comfyui", "a portrait", recipe=recipe)
            assert result.recipe == "comfyui_sdxl_standard"


class TestDrawThingsPath:
    @pytest.mark.asyncio
    async def test_success_returns_job_result(self, tmp_path):
        fake_engine = _fake_drawthings_engine(available=True, data=b"fakepng")

        with (
            patch("mcp.imagen.engines.get", return_value=fake_engine),
            patch(
                "mcp.imagen.io.save_image",
                side_effect=_save_image_to(tmp_path / "dt_out.png"),
            ),
        ):
            result = await run("drawthings", "a bear")

            assert isinstance(result, JobResult)
            assert result.engine == "drawthings"
            assert result.job_id.startswith("job_")
            fake_engine.generate_async.assert_awaited_once_with("a bear")

    @pytest.mark.asyncio
    async def test_drawthings_not_running_raises(self):
        fake_engine = _fake_drawthings_engine(available=False)

        with patch("mcp.imagen.engines.get", return_value=fake_engine):
            with pytest.raises(ImageRunnerError, match="not running"):
                await run("drawthings", "a bear")

    @pytest.mark.asyncio
    async def test_engine_failure_marks_job_failed(self):
        fake_engine = _fake_drawthings_engine(available=True)
        fake_engine.generate_async = AsyncMock(
            side_effect=RuntimeError("comfyui exploded")
        )

        with (
            patch("mcp.imagen.engines.get", return_value=fake_engine),
            pytest.raises(RuntimeError, match="exploded"),
        ):
            await run("drawthings", "a bear")

        jobs = image_jobs.list_recent(limit=1)
        assert len(jobs) == 1
        assert jobs[0].status is ImageJobStatus.FAILED
        assert "exploded" in (jobs[0].normalized_error or "")

    @pytest.mark.asyncio
    async def test_recipe_workflow_template_id_recorded(self, tmp_path):
        recipe = MagicMock()
        recipe.recipe_id = "drawthings_standard"
        recipe.workflow_template_id = "dt_basic"
        fake_engine = _fake_drawthings_engine(available=True, data=b"fakepng")

        with (
            patch("mcp.imagen.engines.get", return_value=fake_engine),
            patch(
                "mcp.imagen.io.save_image",
                side_effect=_save_image_to(tmp_path / "dt_out.png"),
            ),
        ):
            await run("drawthings", "a bear", recipe=recipe)

        jobs = image_jobs.list_recent(limit=1)
        assert len(jobs) == 1
        assert jobs[0].workflow_template_id == "dt_basic"


class TestCharacterPath:
    @pytest.mark.asyncio
    async def test_legacy_character_without_contract_raises(self):
        from gateway.image_character_contracts import CharacterContractError

        with (
            patch(
                "gateway.image_gen.is_available",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "gateway.image_character_contracts.resolve_comfyui_character",
                side_effect=CharacterContractError(
                    "character only has legacy metadata/photos"
                ),
            ),
            patch(
                "gateway.image_character_contracts.comfyui_character_runtime_status",
                new_callable=AsyncMock,
                return_value=(True, "ready"),
            ),
            pytest.raises(ImageRunnerError, match="legacy metadata/photos"),
        ):
            await run("comfyui", "draw my character", character_id="char_abc")

    @pytest.mark.asyncio
    async def test_identity_runtime_must_have_exact_sdxl_adapter(self):
        resolved = {
            "positive_prompt": "person",
            "negative_prompt": "",
            "reference_path": "ref.png",
            "identity_mode": "balanced",
            "width": 1024,
            "height": 1024,
            "steps": 8,
            "guidance": 4.5,
            "recipe_id": "contract-v1",
            "identity_method": "ipadapter_faceid",
            "references": [{"ref_id": "ref-primary"}],
        }
        with (
            patch(
                "gateway.image_gen.is_available",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "gateway.image_character_contracts.resolve_comfyui_character",
                return_value=resolved,
            ),
            patch(
                "gateway.image_character_contracts.comfyui_character_runtime_status",
                new_callable=AsyncMock,
                return_value=(False, "required SDXL adapter is missing"),
            ),
            pytest.raises(ImageRunnerError, match="SDXL adapter is missing"),
        ):
            await run("comfyui", "draw my character", character_id="char_abc")

    @pytest.mark.asyncio
    async def test_character_success_uses_resolved_contract(self, tmp_path):
        resolved = {
            "positive_prompt": "late-thirties man, natural skin texture",
            "negative_prompt": "beautified, waxy skin",
            "reference_path": str(tmp_path / "ref.png"),
            "identity_mode": "balanced",
            "width": 896,
            "height": 1152,
            "steps": 26,
            "guidance": 3.0,
            "recipe_id": "jacob-sdxl-v1",
            "identity_method": "ipadapter_faceid",
            "references": [{"ref_id": "ref-primary"}],
        }

        with (
            patch(
                "gateway.image_gen.is_available",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "gateway.image_character_contracts.resolve_comfyui_character",
                return_value=resolved,
            ),
            patch(
                "gateway.image_character_contracts.comfyui_character_runtime_status",
                new_callable=AsyncMock,
                return_value=(True, "ready"),
            ),
            patch(
                "gateway.image_gen.generate_with_character",
                new_callable=AsyncMock,
            ) as mock_gen,
        ):
            mock_gen.return_value = {
                "prompt_id": "p_char",
                "filename": str(tmp_path / "char_out.png"),
                "job_id": "job_char123",
                "character_weight": 0.7,
            }
            result = await run(
                "comfyui",
                "at a lake",
                character_id="char_abc",
                negative_prompt="hat",
            )

        mock_gen.assert_awaited_once_with(
            prompt="late-thirties man, natural skin texture, at a lake",
            character_ref_path=str(tmp_path / "ref.png"),
            identity_mode="balanced",
            negative_prompt="beautified, waxy skin, hat",
            width=896,
            height=1152,
            steps=26,
            cfg=3.0,
            guidance_tags=None,
        )
        assert result.character_weight == 0.7
        assert result.recipe == "jacob-sdxl-v1"
        assert result.routing_reason == (
            "character contract char_abc: ipadapter_faceid with 1 reference(s)"
        )


class TestValidation:
    @pytest.mark.asyncio
    async def test_unknown_engine_raises(self):
        with pytest.raises(ImageRunnerError, match="unknown engine"):
            await run("midjourney", "a bear")

    @pytest.mark.asyncio
    async def test_invalid_engine_strips_whitespace(self):
        with patch(
            "gateway.image_gen.is_available",
            new_callable=AsyncMock,
            return_value=True,
        ):
            with patch(
                "gateway.image_gen.generate",
                new_callable=AsyncMock,
            ) as mock_gen:
                mock_gen.return_value = {
                    "prompt_id": "p",
                    "filename": "f",
                    "job_id": "j",
                }
                result = await run("  ComfyUI  ", "test")
                assert result.engine == "comfyui"
