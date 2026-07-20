"""IMG-G8 immediate ComfyUI error extraction contracts."""

import pytest

from gateway import image_gen


@pytest.mark.asyncio
async def test_poll_surfaces_comfyui_execution_error(monkeypatch):
    class Response:
        def json(self):
            return {
                "prompt-err": {
                    "status": {"status_str": "error"},
                    "outputs": {},
                    "execution_error": "KSampler: checkpoint missing",
                }
            }

    class Client:
        async def get(self, _url):
            return Response()

    async def no_wait(_seconds):
        return None

    monkeypatch.setattr(image_gen.asyncio, "sleep", no_wait)

    with pytest.raises(RuntimeError, match="checkpoint missing"):
        await image_gen._poll(Client(), "prompt-err", timeout=1)
