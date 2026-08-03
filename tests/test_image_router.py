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
        "flux",
        "openrouter",
    ]
    by_name = {engine["name"]: engine for engine in result["engines"]}
    assert by_name["comfyui"]["available"] is True
    assert by_name["drawthings"]["available"] is False
    # The paid lanes are gated, and an unavailable one has to say why.
    assert by_name["flux"]["available"] is False
    assert by_name["flux"]["unavailable_reason"]
    assert by_name["flux"]["cost_per_image_usd"] < by_name["openrouter"]["cost_per_image_usd"]


@pytest.mark.asyncio
async def test_image_generate_rejects_unknown_engine():
    with pytest.raises(HTTPException, match="engine must be"):
        await extended.image_generate(extended.ImageGenRequest(prompt="cat", engine="unknown"))


@pytest.mark.asyncio
async def test_image_view_serves_persisted_local_artifact(monkeypatch, tmp_path: Path):
    from mcp.imagen.config import settings

    monkeypatch.setattr(settings, "output_dir", tmp_path)
    image = tmp_path / "drawthings_1.png"
    image.write_bytes(b"png")

    response = await extended.image_view(str(image))

    assert Path(response.path) == image
