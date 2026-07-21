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
    assert result["engines"] == [
        {"name": "comfyui", "label": "ComfyUI", "available": True},
        {"name": "drawthings", "label": "Draw Things", "available": False},
    ]


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
