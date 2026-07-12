"""Packet 025 — local-first imagegen pipeline v2 (mocked local server).

These tests prove the criteria-verified loop and the Draw Things engine work
end-to-end WITHOUT a running server or the ~7GB model download. The local
server is faked through the :class:`ImagegenAdapter` interface so the network
boundary is the only thing mocked.

LIVE-VERIFY (skipped here, needs Jacob's Draw Things install):
  - enable API Server in Draw Things (127.0.0.1:7860)
  - run `generate_until` against a real criteria file
  - confirm attempts.jsonl shows real scores and the best image lands in the run folder
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mcp.imagen.engines.adapters import DrawThingsHttpAdapter, ImagegenAdapter
from mcp.imagen.engines.base import RefusalError
from mcp.imagen.engines.drawthings import DrawThingsEngine

# ---------------------------------------------------------------------------
# Mock adapter — stands in for a local Draw Things / A1111 server
# ---------------------------------------------------------------------------


class MockImagegenAdapter:
    """In-memory ImagegenAdapter: no HTTP, no model, deterministic output."""

    def __init__(self, images: list[bytes] | None = None) -> None:
        self.images = images if images is not None else [b"fake-png-bytes"]
        self.txt2img_calls: list[dict] = []
        self.img2img_calls: list[dict] = []

    def txt2img(self, payload: dict) -> list[bytes]:
        self.txt2img_calls.append(payload)
        return self.images

    def img2img(self, payload: dict) -> list[bytes]:
        self.img2img_calls.append(payload)
        return self.images


# ---------------------------------------------------------------------------
# Adapter interface
# ---------------------------------------------------------------------------


def test_drawthings_http_adapter_is_imagegen_adapter():
    from mcp.imagen.config import settings

    adapter = DrawThingsHttpAdapter(settings.dt_url)
    assert isinstance(adapter, ImagegenAdapter)


def test_engine_default_adapter_is_http():
    eng = DrawThingsEngine()
    assert isinstance(eng._adapter, DrawThingsHttpAdapter)


def test_engine_accepts_injected_mock_adapter():
    mock = MockImagegenAdapter()
    eng = DrawThingsEngine(adapter=mock)
    assert eng._adapter is mock
    assert eng.generate("a prompt", seed=7) == b"fake-png-bytes"
    assert mock.txt2img_calls[0]["seed"] == 7


def test_engine_passes_prompt_and_size_to_adapter():
    mock = MockImagegenAdapter()
    eng = DrawThingsEngine(adapter=mock)
    eng.generate("portrait of jace", aspect_ratio="3:4", photorealistic=True)
    payload = mock.txt2img_calls[0]
    assert payload["prompt"].startswith("portrait of jace")
    assert "photorealistic" in payload["prompt"].lower()
    assert payload["width"] == 512
    assert payload["height"] == 682


def test_engine_img2img_uses_adapter_img2img(tmp_path):
    # 1x1 PNG on disk so the engine can read/resize it without a live server.
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
    )
    init = tmp_path / "init.png"
    init.write_bytes(png)

    mock = MockImagegenAdapter()
    eng = DrawThingsEngine(adapter=mock)
    eng.generate("refine", init_image=init)
    assert len(mock.img2img_calls) == 1
    assert "init_images" in mock.img2img_calls[0]


def test_http_adapter_txt2img_decodes_images():
    import base64

    fake_png = base64.b64encode(b"real-png").decode()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"images": [fake_png]}
    with patch("httpx.post", return_value=mock_resp):
        adapter = DrawThingsHttpAdapter("http://dummy:7860")
        out = adapter.txt2img({"prompt": "x"})
    assert out == [b"real-png"]


def test_http_adapter_empty_images_raises_refusal():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"images": []}
    with patch("httpx.post", return_value=mock_resp):
        adapter = DrawThingsHttpAdapter("http://dummy:7860")
        with pytest.raises(RefusalError):
            adapter.txt2img({"prompt": "x"})


def test_http_adapter_connect_error_is_actionable():
    import httpx

    with patch("httpx.post", side_effect=httpx.ConnectError("boom")):
        adapter = DrawThingsHttpAdapter("http://dummy:7860")
        with pytest.raises(RuntimeError, match="Could not reach Draw Things"):
            adapter.txt2img({"prompt": "x"})


# ---------------------------------------------------------------------------
# Full criteria-verified loop — local server faked via the adapter
# ---------------------------------------------------------------------------


def _engine_with_mock_adapter(images: list[bytes]) -> DrawThingsEngine:
    return DrawThingsEngine(adapter=MockImagegenAdapter(images))


def _no_criteria():
    """A criteria where every scorer defaults to a pass (no cfg)."""
    crit = MagicMock()
    crit.face_match = None
    crit.rubric = []
    crit.mechanical = None
    return crit


def test_loop_stops_early_on_pass():
    eng = _engine_with_mock_adapter([b"img-pass"])
    with (
        patch("mcp.imagen.verify.engines.get", return_value=eng),
        patch("mcp.imagen.verify.load_criteria", return_value=_no_criteria()),
        patch("mcp.imagen.verify.score_mechanical", return_value=1.0),
        patch("mcp.imagen.verify.score_face_match", return_value=1.0),
        patch("mcp.imagen.verify.score_vision_rubric", return_value=(1.0, [])),
    ):
        results, _ = _run(prompt="x", criteria_name="c", engine="drawthings", max_attempts=8)
    assert len(results) == 1
    assert results[0]["passed"] is True
    # one generation only — stopped early
    assert eng._adapter.txt2img_calls == [eng._adapter.txt2img_calls[0]]


def test_loop_exhausts_attempts_when_never_passing():
    eng = _engine_with_mock_adapter([b"img-a", b"img-b"])
    with (
        patch("mcp.imagen.verify.engines.get", return_value=eng),
        patch("mcp.imagen.verify.load_criteria", return_value=_no_criteria()),
        patch("mcp.imagen.verify.score_mechanical", return_value=0.0),
        patch("mcp.imagen.verify.score_face_match", return_value=1.0),
        patch("mcp.imagen.verify.score_vision_rubric", return_value=(0.0, [])),
    ):
        _run(prompt="x", criteria_name="c", engine="drawthings", max_attempts=4)
    # mechanical<0.5 short-circuits; loop should run all max_attempts
    assert len(eng._adapter.txt2img_calls) == 4


def test_loop_keeps_best_n_and_sorts():
    eng = _engine_with_mock_adapter([b"img0", b"img1", b"img2", b"img3"])

    def face_score(_data: bytes, _cfg: Any) -> float:
        # score rises with the first byte of the image, giving a stable ordering
        return float(_data[3]) / 255.0

    with (
        patch("mcp.imagen.verify.engines.get", return_value=eng),
        patch("mcp.imagen.verify.load_criteria", return_value=_no_criteria()),
        patch("mcp.imagen.verify.score_mechanical", return_value=1.0),
        patch("mcp.imagen.verify.score_face_match", side_effect=face_score),
        # rubric below 0.5 so nothing passes; loop exhausts and keeps best-N
        patch("mcp.imagen.verify.score_vision_rubric", return_value=(0.3, [])),
    ):
        results, _ = _run(prompt="x", criteria_name="c", engine="drawthings", max_attempts=4, keep=2)
    assert len(results) == 2
    # best score (highest face score) first
    first = results[0]["scores"]["face_match"]
    second = results[1]["scores"]["face_match"]
    assert first >= second


def test_loop_writes_attempts_jsonl():
    import json

    eng = _engine_with_mock_adapter([b"img-pass"])
    with (
        patch("mcp.imagen.verify.engines.get", return_value=eng),
        patch("mcp.imagen.verify.load_criteria", return_value=_no_criteria()),
        patch("mcp.imagen.verify.score_mechanical", return_value=1.0),
        patch("mcp.imagen.verify.score_face_match", return_value=1.0),
        patch("mcp.imagen.verify.score_vision_rubric", return_value=(1.0, [])),
    ):
        results, home = _run(prompt="x", criteria_name="c", engine="drawthings", max_attempts=3)

    # run-id is a random uuid; find the single run dir that was created.
    run_dirs = list((home / "Pictures" / "kitty-gen" / "runs").glob("*"))
    assert len(run_dirs) == 1
    log_path = run_dirs[0] / "attempts.jsonl"
    assert log_path.exists()
    lines = log_path.read_text().strip().split("\n")
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["passed"] is True
    assert "scores" in entry


def test_loop_private_true_blocks_cloud_engine():
    from mcp.imagen.verify import generate_until

    with patch("mcp.imagen.verify.load_criteria", return_value=_no_criteria()):
        with pytest.raises(ValueError, match="private=True"):
            generate_until(
                prompt="x",
                criteria_name="c",
                engine="nano_banana",
                private=True,
            )


# ---------------------------------------------------------------------------
# Test helper — wraps verify.generate_until with a tmp run dir
# ---------------------------------------------------------------------------


def _run(**kwargs: Any) -> tuple[list[dict], Path]:
    import tempfile

    from mcp.imagen.verify import generate_until

    # Each run gets an isolated fake home so attempts.jsonl lands somewhere we
    # can assert on, with no real ~/Pictures writes.
    home = Path(tempfile.mkdtemp(prefix="kitty-imgtest-"))
    with patch("mcp.imagen.verify.Path.home", return_value=home):
        return generate_until(**kwargs), home
