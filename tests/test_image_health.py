"""IMG-06 renderer health and workflow compatibility contracts."""

from __future__ import annotations

import pytest

from gateway import image_gen


@pytest.mark.asyncio
async def test_comfy_health_requires_workflow_nodes(monkeypatch):
    class Response:
        status_code = 200

        def json(self):
            return {"SaveImage": {}, "KSampler": {}}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def get(self, url: str):
            assert url.endswith("/system_stats") or url.endswith("/object_info")
            return Response()

    monkeypatch.setattr(image_gen.httpx, "AsyncClient", lambda **_kwargs: Client())

    assert await image_gen.is_available() is False


@pytest.mark.asyncio
async def test_comfy_health_accepts_required_workflow_nodes(monkeypatch):
    class Response:
        status_code = 200

        def json(self):
            return {node: {} for node in image_gen.COMFY_REQUIRED_NODES}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def get(self, _url: str):
            return Response()

    monkeypatch.setattr(image_gen.httpx, "AsyncClient", lambda **_kwargs: Client())

    assert await image_gen.is_available() is True
