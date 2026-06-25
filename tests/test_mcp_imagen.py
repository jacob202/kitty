"""Tests for mcp/imagen/server.py — pure logic and mocked API paths."""

from __future__ import annotations

import importlib
import sys
import types as _types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Stub out mcp and google.genai so tests run without the real SDKs installed
# ---------------------------------------------------------------------------

class _Image:
    """Minimal Image stand-in so isinstance checks work without the real mcp package."""
    def __init__(self, data: bytes, format: str) -> None:
        self.data = data
        self.format = format


class _FastMCPStub:
    """FastMCP stub whose tool() decorator is transparent (returns the function unchanged)."""
    def __init__(self, *args, **kwargs):
        pass

    def tool(self, *args, **kwargs):
        def decorator(func):
            return func
        return decorator

    def run(self):
        pass


@pytest.fixture(autouse=True)
def _sdk_stubs():
    """Inject mcp.server.fastmcp and google.genai stubs into sys.modules."""
    # --- mcp stubs ---
    stub_fastmcp_mod = _types.ModuleType("mcp.server.fastmcp")
    stub_fastmcp_mod.FastMCP = _FastMCPStub  # type: ignore[attr-defined]
    stub_fastmcp_mod.Image = _Image  # type: ignore[attr-defined]

    stub_server_mod = _types.ModuleType("mcp.server")
    stub_mcp_mod = _types.ModuleType("mcp")

    # --- google.genai stubs ---
    stub_types = MagicMock(name="google.genai.types")
    stub_types.Part = MagicMock()
    stub_types.Part.from_bytes = MagicMock(return_value=MagicMock())
    stub_types.Part.from_text = MagicMock(return_value=MagicMock())
    stub_types.GenerateContentConfig = MagicMock(return_value=MagicMock())
    stub_types.ImageConfig = MagicMock(return_value=MagicMock())
    stub_types.GenerateImagesConfig = MagicMock(return_value=MagicMock())

    stub_genai = MagicMock(name="google.genai")
    stub_genai.types = stub_types
    stub_genai.Client = MagicMock()

    stub_google = _types.ModuleType("google")
    stub_google.genai = stub_genai  # type: ignore[attr-defined]

    keys = (
        "mcp", "mcp.server", "mcp.server.fastmcp",
        "google", "google.genai", "google.genai.types",
    )
    prev = {k: sys.modules.get(k) for k in keys}
    sys.modules["mcp"] = stub_mcp_mod
    sys.modules["mcp.server"] = stub_server_mod
    sys.modules["mcp.server.fastmcp"] = stub_fastmcp_mod
    sys.modules["google"] = stub_google
    sys.modules["google.genai"] = stub_genai
    sys.modules["google.genai.types"] = stub_types

    yield

    for k, v in prev.items():
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v

# ---------------------------------------------------------------------------
# Module loading helper
# ---------------------------------------------------------------------------

def _load_server():
    """Import the imagen server fresh so monkeypatching doesn't bleed between tests."""
    if "server" in sys.modules:
        del sys.modules["server"]
    spec = importlib.util.spec_from_file_location(
        "server",
        Path(__file__).parent.parent / "mcp" / "imagen" / "server.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def srv():
    return _load_server()


# ---------------------------------------------------------------------------
# _seed
# ---------------------------------------------------------------------------

def test_seed_is_positive_int(srv):
    s = srv._seed()
    assert isinstance(s, int)
    assert s >= 0


def test_seed_varies(srv):
    seeds = {srv._seed() for _ in range(10)}
    assert len(seeds) > 1, "ten seeds should not all be identical"


# ---------------------------------------------------------------------------
# _parse_comfy keyword dispatch
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("prompt,key,expected", [
    ("a realistic portrait", "sdxl", True),
    ("sdxl landscape photo", "sdxl", True),
    ("a bear in the woods", "sdxl", False),
    ("explicit nude scene", "explicit", True),
    ("erect male figure", "explicit", True),
    ("a soft portrait", "explicit", False),
    ("portrait of a woman", "h", 768),       # SD1.5 portrait: 512×768
    ("landscape mountain scene", "w", 768),  # SD1.5 landscape: 768×512
])
def test_parse_comfy_flags(srv, prompt, key, expected):
    result = srv._parse_comfy(prompt)
    assert result[key] == expected


def test_parse_comfy_sdxl_resolution(srv):
    p = srv._parse_comfy("photorealistic sdxl portrait")
    assert p["w"] == 832
    assert p["h"] == 1216
    assert p["steps"] >= 6


def test_parse_comfy_sd15_defaults(srv):
    p = srv._parse_comfy("a simple bear")
    assert p["sdxl"] is False
    assert p["w"] == 512
    assert p["h"] == 512
    assert p["steps"] == 25
    assert p["cfg"] == 7.0


def test_parse_comfy_bear_strength(srv):
    assert srv._parse_comfy("more bear")["lstr"] == 1.0
    assert srv._parse_comfy("less bear")["lstr"] == 0.5
    assert srv._parse_comfy("a bear")["lstr"] == 0.8


def test_parse_comfy_fast_reduces_steps(srv):
    p = srv._parse_comfy("a fast drawing")
    assert p["steps"] == 15


def test_parse_comfy_detailed_increases_steps(srv):
    p = srv._parse_comfy("a detailed portrait")
    assert p["steps"] == 35


# ---------------------------------------------------------------------------
# Workflow builders
# ---------------------------------------------------------------------------

def test_wf_sd15_structure(srv):
    p = srv._parse_comfy("a bear")
    wf = srv._wf_sd15("a bear", p)
    assert "1" in wf  # checkpoint loader
    assert "4" in wf  # bear LoRA
    assert "6" in wf  # KSampler
    assert "8" in wf  # SaveImage
    assert "9" not in wf  # explicit LoRA not added


def test_wf_sd15_explicit_adds_node(srv):
    p = srv._parse_comfy("explicit nude")
    wf = srv._wf_sd15("explicit nude", p)
    assert "9" in wf
    assert wf["9"]["class_type"] == "LoraLoader"


def test_wf_sdxl_structure(srv):
    p = srv._parse_comfy("realistic sdxl scene")
    wf = srv._wf_sdxl("realistic sdxl scene", p)
    assert "1" in wf  # checkpoint
    assert "5" in wf  # KSampler
    assert "7" in wf  # SaveImage
    ckpt = wf["1"]["inputs"]["ckpt_name"]
    assert ckpt == srv.SDXL_PHOTONIC


# ---------------------------------------------------------------------------
# _first_image_bytes / _refusal_text — response parsing
# ---------------------------------------------------------------------------

def _fake_response(has_image: bool, text: str = ""):
    """Build a minimal fake Gemini generate_content response."""
    part = MagicMock()
    if has_image:
        part.inline_data = MagicMock(data=b"fake-image-bytes")
        part.text = None
    else:
        part.inline_data = None
        part.text = text

    candidate = MagicMock()
    candidate.content.parts = [part]

    resp = MagicMock()
    resp.candidates = [candidate]
    return resp


def test_first_image_bytes_present(srv):
    resp = _fake_response(has_image=True)
    assert srv._first_image_bytes(resp) == b"fake-image-bytes"


def test_first_image_bytes_absent(srv):
    resp = _fake_response(has_image=False, text="safety refusal")
    assert srv._first_image_bytes(resp) is None


def test_refusal_text_extracted(srv):
    resp = _fake_response(has_image=False, text="content policy violation")
    assert srv._refusal_text(resp) == "content policy violation"


def test_refusal_text_empty_candidates(srv):
    resp = MagicMock()
    resp.candidates = []
    assert srv._refusal_text(resp) == "no image and no explanation returned"


# ---------------------------------------------------------------------------
# _save
# ---------------------------------------------------------------------------

def test_save_writes_file(srv, tmp_path):
    with patch.object(srv, "OUTPUT_DIR", tmp_path):
        path = srv._save(b"png-bytes", "test")
    assert path.exists()
    assert path.read_bytes() == b"png-bytes"
    assert path.name.startswith("test_")
    assert path.suffix == ".png"


# ---------------------------------------------------------------------------
# set_avatar / generate_with_avatar
# ---------------------------------------------------------------------------

def test_set_avatar_missing_file(srv):
    result = srv.set_avatar("/nonexistent/path/avatar.png")
    assert "not found" in result.lower()


def test_set_avatar_copies_file(srv, tmp_path):
    src = tmp_path / "face.png"
    src.write_bytes(b"fake-png")
    out_dir = tmp_path / "output"
    avatar = out_dir / "_avatar.png"

    with (
        patch.object(srv, "OUTPUT_DIR", out_dir),
        patch.object(srv, "AVATAR_PATH", avatar),
    ):
        result = srv.set_avatar(str(src))

    assert avatar.exists()
    assert avatar.read_bytes() == b"fake-png"
    assert "avatar set" in result.lower()


def test_generate_with_avatar_no_avatar_set(srv, tmp_path):
    avatar = tmp_path / "_avatar.png"
    with patch.object(srv, "AVATAR_PATH", avatar):
        result = srv.generate_with_avatar("in a forest")
    assert any("no avatar" in str(r).lower() for r in result)


# ---------------------------------------------------------------------------
# generate_image — mocked Gemini
# ---------------------------------------------------------------------------

def test_generate_image_returns_image_and_path(srv, tmp_path):
    fake_resp = _fake_response(has_image=True)
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = fake_resp

    with (
        patch.object(srv, "_gemini_client", return_value=mock_client),
        patch.object(srv, "_save", return_value=tmp_path / "nano_123.png"),
    ):
        result = srv.generate_image("a misty harbor")

    assert any(isinstance(r, _Image) for r in result)
    assert any("Saved to:" in str(r) for r in result)


def test_generate_image_refusal_returns_message(srv):
    fake_resp = _fake_response(has_image=False, text="content policy")
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = fake_resp

    with patch.object(srv, "_gemini_client", return_value=mock_client):
        result = srv.generate_image("something refused")

    assert len(result) == 1
    assert "No image generated" in result[0]
    assert "content policy" in result[0]


# ---------------------------------------------------------------------------
# edit_image — mocked Gemini
# ---------------------------------------------------------------------------

def test_edit_image_missing_file(srv):
    result = srv.edit_image("/nonexistent/image.png", "make it blue")
    assert any("not found" in str(r).lower() for r in result)


def test_edit_image_success(srv, tmp_path):
    src = tmp_path / "source.png"
    src.write_bytes(b"fake-png-bytes")
    fake_resp = _fake_response(has_image=True)
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = fake_resp

    with (
        patch.object(srv, "_gemini_client", return_value=mock_client),
        patch.object(srv, "_save", return_value=tmp_path / "edit_123.png"),
    ):
        result = srv.edit_image(str(src), "make it nighttime")

    assert any(isinstance(r, _Image) for r in result)


# ---------------------------------------------------------------------------
# generate_with_reference
# ---------------------------------------------------------------------------

def test_generate_with_reference_missing_file(srv):
    result = srv.generate_with_reference(["/no/such/file.png"], "a new scene")
    assert any("not found" in str(r).lower() for r in result)


def test_generate_with_reference_success(srv, tmp_path):
    ref = tmp_path / "ref.png"
    ref.write_bytes(b"fake-png")
    fake_resp = _fake_response(has_image=True)
    mock_nano = MagicMock(return_value=(b"generated-bytes", ""))

    with (
        patch.object(srv, "_nano_image", mock_nano),
        patch.object(srv, "_save", return_value=tmp_path / "ref_123.png"),
        patch.object(srv, "_image_part", return_value=MagicMock()),
    ):
        result = srv.generate_with_reference([str(ref)], "in Paris at night")

    assert any(isinstance(r, _Image) for r in result)


# ---------------------------------------------------------------------------
# variations
# ---------------------------------------------------------------------------

def test_variations_missing_file(srv):
    result = srv.variations("/no/such/file.png", count=2)
    assert any("not found" in str(r).lower() for r in result)


def test_variations_count_clamp(srv, tmp_path):
    src = tmp_path / "source.png"
    src.write_bytes(b"fake-png")

    calls = []

    def fake_nano(contents):
        calls.append(1)
        return (b"var-bytes", "")

    with (
        patch.object(srv, "_nano_image", side_effect=fake_nano),
        patch.object(srv, "_save", return_value=tmp_path / "var_123.png"),
        patch.object(srv, "_image_part", return_value=MagicMock()),
    ):
        result = srv.variations(str(src), count=10)

    assert len(calls) == 4  # clamped to max 4


# ---------------------------------------------------------------------------
# make_gallery
# ---------------------------------------------------------------------------

def test_make_gallery_no_images(srv, tmp_path):
    with patch.object(srv, "OUTPUT_DIR", tmp_path):
        result = srv.make_gallery()
    assert "generate something first" in result.lower()


def test_make_gallery_builds_html(srv, tmp_path):
    (tmp_path / "nano_001.png").write_bytes(b"x")
    (tmp_path / "nano_002.png").write_bytes(b"x")

    with patch.object(srv, "OUTPUT_DIR", tmp_path), patch.object(srv, "AVATAR_PATH", tmp_path / "_avatar.png"):
        result = srv.make_gallery()

    gallery = tmp_path / "gallery.html"
    assert gallery.exists()
    content = gallery.read_text()
    assert "nano_001.png" in content
    assert "nano_002.png" in content
    assert "2 images" in result


# ---------------------------------------------------------------------------
# _gemini_client — API key guard
# ---------------------------------------------------------------------------

def test_gemini_client_raises_without_key(srv):
    with (
        patch.dict("os.environ", {}, clear=True),
        pytest.raises(RuntimeError, match="GEMINI_API_KEY"),
    ):
        srv._gemini_client()


def test_openai_client_raises_without_key(srv):
    with (
        patch.dict("os.environ", {}, clear=True),
        pytest.raises(RuntimeError, match="OPENAI_API_KEY"),
    ):
        srv._openai_client()
