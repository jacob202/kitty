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
            result = await run(
                "comfyui",
                "a landscape",
                plan_id="imgplan_comfy",
                intent_json='{"intent_version":1,"operation":"txt2img"}',
            )

            assert isinstance(result, JobResult)
            assert result.engine == "comfyui"
            assert result.filename == str(tmp_path / "out.png")
            mock_gen.assert_awaited_once_with(
                "a landscape",
                parent_id=None,
                guidance_tags=None,
                project_id=None,
                plan_id="imgplan_comfy",
                intent_json='{"intent_version":1,"operation":"txt2img"}',
            )

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
            result = await run(
                "drawthings",
                "a bear",
                plan_id="imgplan_drawthings",
                intent_json='{"intent_version":1,"operation":"txt2img"}',
            )

            assert isinstance(result, JobResult)
            assert result.engine == "drawthings"
            assert result.job_id.startswith("job_")
            fake_engine.generate_async.assert_awaited_once_with("a bear")
            job = image_jobs.get_job(result.job_id)
            assert job is not None
            assert job.plan_id == "imgplan_drawthings"
            assert job.intent_json == '{"intent_version":1,"operation":"txt2img"}'

    @pytest.mark.asyncio
    async def test_drawthings_not_running_raises(self):
        fake_engine = _fake_drawthings_engine(available=False)

        with patch("mcp.imagen.engines.get", return_value=fake_engine):
            with pytest.raises(ImageRunnerError, match="not running"):
                await run("drawthings", "a bear")

    @pytest.mark.asyncio
    async def test_engine_failure_marks_job_failed(self):
        fake_engine = _fake_drawthings_engine(available=True)
        fake_engine.generate_async = AsyncMock(side_effect=RuntimeError("comfyui exploded"))

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


class TestHostedRegistryPaths:
    @pytest.mark.asyncio
    async def test_airforce_success_uses_registered_engine(self, tmp_path, monkeypatch):
        fake_engine = MagicMock()
        fake_engine.model_name = "grok-imagine-image-2.0"
        fake_engine.generate_async = AsyncMock(return_value=b"airforce-png")
        monkeypatch.setenv("KITTY_IMAGE_AIRFORCE_ENABLED", "1")
        monkeypatch.setenv("AIRFORCE_API_KEY", "test-key")

        with (
            patch("gateway.image_runner.paid_engine_available", return_value=(True, "")),
            patch("mcp.imagen.engines.get", return_value=fake_engine),
            patch(
                "mcp.imagen.io.save_image", side_effect=_save_image_to(tmp_path / "airforce.png")
            ),
        ):
            result = await run(
                "airforce",
                "a red panda coding",
                plan_id="imgplan_airforce",
                intent_json='{"intent_version":1,"operation":"txt2img"}',
            )

        assert result.engine == "airforce"
        assert result.filename == str(tmp_path / "airforce.png")
        fake_engine.generate_async.assert_awaited_once_with("a red panda coding")
        job = image_jobs.list_recent(limit=1)[0]
        assert job.provider == "airforce"
        assert job.plan_id == "imgplan_airforce"
        assert job.intent_json == '{"intent_version":1,"operation":"txt2img"}'

    @pytest.mark.asyncio
    async def test_fal_character_uses_bound_reference(self, tmp_path, monkeypatch):
        ref = tmp_path / "identity.png"
        ref.write_bytes(b"reference")
        import io

        from PIL import Image

        image_buf = io.BytesIO()
        Image.new("RGB", (1024, 1024), "white").save(image_buf, format="PNG")
        fake_engine = MagicMock()
        fake_engine.model_name = "fal-ai/flux-pulid"
        fake_engine.generate_async = AsyncMock(return_value=image_buf.getvalue())
        monkeypatch.setenv("KITTY_IMAGE_FAL_ENABLED", "1")
        monkeypatch.setenv("FAL_KEY", "test-key")

        with (
            patch("gateway.image_runner.paid_engine_available", return_value=(True, "")),
            patch("mcp.imagen.engines.get", return_value=fake_engine),
            patch("mcp.imagen.io.save_image", side_effect=_save_image_to(tmp_path / "fal.png")),
        ):
            result = await run(
                "fal",
                "same fictional person outdoors",
                character_id="char_test",
                character_ref_path=str(ref),
                negative_prompt="blurry",
            )

        assert result.engine == "fal"
        assert result.cost_usd == pytest.approx(0.0666)
        assert result.cost_source == "provider_contract"
        job = image_jobs.list_recent(limit=1)[0]
        assert (job.width, job.height) == (1024, 1024)
        fake_engine.generate_async.assert_awaited_once_with(
            "same fictional person outdoors",
            identity_images=[ref],
            negative_prompt="blurry",
        )
        assert image_jobs.list_recent(limit=1)[0].provider == "fal"

    @pytest.mark.asyncio
    async def test_fal_requires_character_reference(self, monkeypatch):
        monkeypatch.setenv("KITTY_IMAGE_FAL_ENABLED", "1")
        monkeypatch.setenv("FAL_KEY", "test-key")
        with pytest.raises(ImageRunnerError, match="character reference"):
            await run("fal", "portrait")


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
                side_effect=CharacterContractError("character only has legacy metadata/photos"),
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
                plan_id="imgplan_character",
                intent_json='{"intent_version":1,"operation":"txt2img"}',
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
            project_id=None,
            plan_id="imgplan_character",
            intent_json='{"intent_version":1,"operation":"txt2img"}',
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


class TestDirectHostedProvenance:
    @pytest.mark.asyncio
    async def test_openrouter_job_keeps_approved_plan_provenance(self, monkeypatch):
        import base64

        class Response:
            status_code = 200
            text = ""

            def json(self):
                image = base64.b64encode(b"png-bytes").decode()
                return {
                    "choices": [
                        {
                            "message": {
                                "images": [{"image_url": {"url": f"data:image/png;base64,{image}"}}]
                            }
                        }
                    ],
                    "usage": {"cost": 0.0},
                }

        class Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            async def post(self, *_args, **_kwargs):
                return Response()

        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.setattr("gateway.image_runner.openrouter_images_available", lambda: (True, ""))
        monkeypatch.setattr("httpx.AsyncClient", lambda *a, **k: Client())

        result = await run(
            "openrouter",
            "a portrait",
            plan_id="imgplan_openrouter",
            intent_json='{"intent_version":1,"operation":"txt2img"}',
        )

        job = image_jobs.get_job(result.job_id)
        assert job is not None
        assert job.plan_id == "imgplan_openrouter"
        assert job.intent_json == '{"intent_version":1,"operation":"txt2img"}'

    @pytest.mark.asyncio
    async def test_legacy_flux_job_keeps_approved_plan_provenance(self, monkeypatch):
        class Response:
            def __init__(self, *, payload=None, content=b"", status_code=200):
                self._payload = payload or {}
                self.content = content
                self.status_code = status_code
                self.text = ""

            def json(self):
                return self._payload

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise RuntimeError(self.status_code)

        class Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            async def post(self, *_args, **_kwargs):
                return Response(payload={"polling_url": "https://poll", "cost": 1.0})

            async def get(self, url, **_kwargs):
                if url == "https://poll":
                    return Response(
                        payload={"status": "Ready", "result": {"sample": "https://sample"}}
                    )
                return Response(content=b"flux-png")

        monkeypatch.setenv("BFL_API_KEY", "test-key")
        monkeypatch.setattr("gateway.image_runner.flux_images_available", lambda: (True, ""))
        monkeypatch.setattr("httpx.AsyncClient", lambda *a, **k: Client())

        result = await run(
            "flux",
            "a portrait",
            plan_id="imgplan_flux_legacy",
            intent_json='{"intent_version":1,"operation":"txt2img"}',
        )

        job = image_jobs.get_job(result.job_id)
        assert job is not None
        assert job.plan_id == "imgplan_flux_legacy"
        assert job.intent_json == '{"intent_version":1,"operation":"txt2img"}'
