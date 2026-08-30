"""IMG-05/06 gateway image-engine routing contracts."""

from pathlib import Path

import pytest
from fastapi import HTTPException

from gateway.routes import extended


@pytest.mark.asyncio
async def test_image_status_reports_each_engine(monkeypatch):
    async def comfy_available():
        return True

    class Adapter:
        def is_available(self):
            return False

    class DrawThings:
        _adapter = Adapter()

    monkeypatch.setattr("gateway.image_gen.is_available", comfy_available)
    monkeypatch.setattr("mcp.imagen.engines.get", lambda name: DrawThings())

    result = await extended.image_status()

    assert result["available"] is True
    # Local engines first because they are free, then the hosted lanes cheapest
    # first. Each hosted entry carries its price so the caller can see what a
    # generation costs before enabling it.
    assert [engine["name"] for engine in result["engines"]] == [
        "comfyui",
        "drawthings",
        "airforce",
        "flux",
        "fal",
        "openrouter",
    ]
    by_name = {engine["name"]: engine for engine in result["engines"]}
    assert by_name["comfyui"]["available"] is True
    assert by_name["drawthings"]["available"] is False
    # The paid lanes are gated, and an unavailable one has to say why.
    assert by_name["flux"]["available"] is False
    assert by_name["flux"]["unavailable_reason"]
    assert by_name["flux"]["cost_per_image_usd"] < by_name["openrouter"]["cost_per_image_usd"]
    # PuLID is billed per output megapixel, rounded up. Kitty's default 1:1
    # square_hd output is 1024x1024 (>1 MP), so it incurs two billable MP.
    fal = by_name["fal"]
    assert fal["cost_per_megapixel_usd"] == pytest.approx(0.0333)
    assert fal["cost_per_image_usd"] == pytest.approx(0.0666)


@pytest.mark.asyncio
async def test_offline_local_engines_say_what_to_do_next(monkeypatch):
    # "no image engine is online" with no reason leaves the user nothing to act
    # on. Every offline engine has to carry its own recovery action, not just
    # the paid ones.
    async def comfy_available():
        return False

    class Adapter:
        def is_available(self):
            return False

    class DrawThings:
        _adapter = Adapter()

    monkeypatch.setattr("gateway.image_gen.is_available", comfy_available)
    monkeypatch.setattr("mcp.imagen.engines.get", lambda name: DrawThings())

    result = await extended.image_status()

    assert result["available"] is False
    by_name = {engine["name"]: engine for engine in result["engines"]}
    for name in ("comfyui", "drawthings", "airforce", "flux", "fal", "openrouter"):
        assert by_name[name]["available"] is False
        assert by_name[name]["unavailable_reason"], f"{name} is offline without a reason"
    assert "Start ComfyUI" in by_name["comfyui"]["unavailable_reason"]
    assert "Draw Things app" in by_name["drawthings"]["unavailable_reason"]


@pytest.mark.asyncio
async def test_available_local_engine_carries_no_offline_reason(monkeypatch):
    async def comfy_available():
        return True

    class Adapter:
        def is_available(self):
            return True

    class DrawThings:
        _adapter = Adapter()

    monkeypatch.setattr("gateway.image_gen.is_available", comfy_available)
    monkeypatch.setattr("mcp.imagen.engines.get", lambda name: DrawThings())

    result = await extended.image_status()

    by_name = {engine["name"]: engine for engine in result["engines"]}
    assert by_name["comfyui"]["unavailable_reason"] is None
    assert by_name["drawthings"]["unavailable_reason"] is None


@pytest.mark.asyncio
async def test_image_generate_rejects_unknown_engine():
    with pytest.raises(HTTPException, match="engine must be"):
        await extended.image_generate(extended.ImageGenRequest(prompt="cat", engine="unknown"))


@pytest.mark.asyncio
async def test_legacy_image_generate_rejects_hosted_engine_before_dispatch(monkeypatch):
    async def should_not_run(*_args, **_kwargs):
        raise AssertionError("hosted engine reached image_runner.run through legacy route")

    monkeypatch.setattr("gateway.image_runner.run", should_not_run)

    with pytest.raises(HTTPException) as exc_info:
        await extended.image_generate(extended.ImageGenRequest(prompt="cat", engine="fal"))

    assert exc_info.value.status_code == 409
    assert "Studio" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_image_view_serves_persisted_local_artifact(monkeypatch, tmp_path: Path):
    from mcp.imagen.config import settings

    monkeypatch.setattr(settings, "output_dir", tmp_path)
    image = tmp_path / "drawthings_1.png"
    image.write_bytes(b"png")

    response = await extended.image_view(str(image))

    assert Path(response.path) == image
