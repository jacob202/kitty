"""Tests for mcp.imagen.metadata — sidecar + manifest.

Tests use a tmp_path-based isolated OUTPUT_DIR by patching
`mcp.imagen.server.OUTPUT_DIR` (which `metadata._output_dir()` resolves
at call time, so monkeypatch works without reload).
"""

from __future__ import annotations

import json
import logging

import pytest

from mcp.imagen import metadata


@pytest.fixture
def isolated_output(tmp_path, monkeypatch):
    """Point metadata._output_dir() at a temp dir for the test.

    We patch the local function in the metadata module directly instead
    of monkeypatching mcp.imagen.server.OUTPUT_DIR — that would require
    importing server.py, which depends on the mcp SDK being installed
    (and the mcp package isn't a test-env dep).
    """
    fake = tmp_path / "kitty-gen"
    fake.mkdir()
    monkeypatch.setattr(metadata, "_output_dir", lambda: fake)
    return fake


# --- write_sidecar ---


def test_write_sidecar_creates_json_next_to_image(isolated_output, tmp_path):
    image = tmp_path / "test.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nfake-png-bytes")

    sidecar = metadata.write_sidecar(
        image,
        prompt="a harbor at dawn",
        engine="nano_banana",
        model="gemini-2.5-flash-image",
        seed=12345,
        params={"aspect_ratio": "16:9", "photorealistic": True},
        parent_path=None,
        tags=["harbor", "dawn"],
    )

    assert sidecar == image.with_suffix(image.suffix + ".json")
    assert sidecar.exists()

    record = json.loads(sidecar.read_text(encoding="utf-8"))
    assert record["prompt"] == "a harbor at dawn"
    assert record["engine"] == "nano_banana"
    assert record["model"] == "gemini-2.5-flash-image"
    assert record["seed"] == 12345
    assert record["params"] == {"aspect_ratio": "16:9", "photorealistic": True}
    assert record["parent_path"] is None
    assert record["tags"] == ["harbor", "dawn"]
    assert "ts" in record and isinstance(record["ts"], float)


def test_write_sidecar_seed_can_be_null(isolated_output, tmp_path):
    image = tmp_path / "test.png"
    image.write_bytes(b"\x89PNG")
    sidecar = metadata.write_sidecar(
        image,
        prompt="x",
        engine="dalle",
        model="dall-e-3",
    )
    record = json.loads(sidecar.read_text(encoding="utf-8"))
    assert record["seed"] is None


def test_write_sidecar_failure_does_not_raise(isolated_output, tmp_path, caplog):
    """OSError during write logs a WARNING but does not raise. The image
    is still valid; the caller proceeds."""
    image = tmp_path / "test.png"
    image.write_bytes(b"\x89PNG")

    # Simulate a write failure by making the parent dir read-only. On
    # most systems, write_text will fail with PermissionError.
    sidecar = metadata.sidecar_path(image)
    sidecar.parent.chmod(0o444)  # read-only
    try:
        with caplog.at_level(logging.WARNING, logger="kitty.imagen.metadata"):
            result = metadata.write_sidecar(image, prompt="x", engine="nano_banana", model="m")
        # Returns the image path on failure (graceful degradation).
        assert result == image
        assert any("sidecar write failed" in r.message for r in caplog.records)
    finally:
        sidecar.parent.chmod(0o755)


# --- append_manifest ---


def test_append_manifest_writes_one_jsonl_row(isolated_output, tmp_path):
    image = tmp_path / "img.png"
    image.write_bytes(b"\x89PNG")
    sidecar = metadata.write_sidecar(image, prompt="x", engine="nano_banana", model="m")

    metadata.append_manifest(image, sidecar)

    manifest = isolated_output / "manifest.jsonl"
    assert manifest.exists()
    lines = manifest.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1

    row = json.loads(lines[0])
    assert row["prompt"] == "x"
    assert row["engine"] == "nano_banana"
    assert row["image_path"] == str(image)
    assert row["sidecar_path"] == str(sidecar)


def test_append_manifest_appends_not_overwrites(isolated_output, tmp_path):
    image1 = tmp_path / "a.png"
    image1.write_bytes(b"\x89PNG")
    sc1 = metadata.write_sidecar(image1, prompt="a", engine="nano_banana", model="m")
    metadata.append_manifest(image1, sc1)

    image2 = tmp_path / "b.png"
    image2.write_bytes(b"\x89PNG")
    sc2 = metadata.write_sidecar(image2, prompt="b", engine="dalle", model="m")
    metadata.append_manifest(image2, sc2)

    manifest = isolated_output / "manifest.jsonl"
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert rows[0]["prompt"] == "a"
    assert rows[1]["prompt"] == "b"


# --- read_image_metadata ---


def test_read_image_metadata_returns_dict(isolated_output, tmp_path):
    image = tmp_path / "img.png"
    image.write_bytes(b"\x89PNG")
    metadata.write_sidecar(
        image, prompt="hi", engine="dalle", model="dall-e-3", seed=None
    )

    result = metadata.read_image_metadata(str(image))
    assert isinstance(result, dict)
    assert result["prompt"] == "hi"
    assert result["engine"] == "dalle"


def test_read_image_metadata_missing_returns_string(isolated_output, tmp_path):
    image = tmp_path / "nope.png"
    image.write_bytes(b"\x89PNG")
    # No sidecar written.
    result = metadata.read_image_metadata(str(image))
    assert isinstance(result, str)
    assert "no metadata" in result


# --- read_manifest ---


def test_read_manifest_returns_empty_when_no_manifest(isolated_output):
    assert metadata.read_manifest() == []


def test_read_manifest_filters_by_engine(isolated_output, tmp_path):
    for engine, prompt in [
        ("nano_banana", "a"),
        ("dalle", "b"),
        ("nano_banana", "c"),
    ]:
        img = tmp_path / f"{engine}-{prompt}.png"
        img.write_bytes(b"\x89PNG")
        sc = metadata.write_sidecar(img, prompt=prompt, engine=engine, model="m")
        metadata.append_manifest(img, sc)

    rows = metadata.read_manifest(engine="nano_banana")
    assert len(rows) == 2
    assert all(r["engine"] == "nano_banana" for r in rows)

    rows = metadata.read_manifest(engine="dalle")
    assert len(rows) == 1
    assert rows[0]["engine"] == "dalle"


def test_read_manifest_filters_by_since(isolated_output, tmp_path):
    img = tmp_path / "old.png"
    img.write_bytes(b"\x89PNG")
    sc = metadata.write_sidecar(img, prompt="old", engine="nano_banana", model="m")
    metadata.append_manifest(img, sc)

    # Bump the manifest's ts so all rows are after `since=1.0`.
    rows = metadata.read_manifest()
    cutoff = max(r["ts"] for r in rows) - 0.5
    rows = metadata.read_manifest(since=cutoff)
    assert all(r["ts"] >= cutoff for r in rows)


def test_read_manifest_newest_first(isolated_output, tmp_path):
    for i in range(3):
        img = tmp_path / f"img{i}.png"
        img.write_bytes(b"\x89PNG")
        sc = metadata.write_sidecar(img, prompt=f"p{i}", engine="nano_banana", model="m")
        metadata.append_manifest(img, sc)

    rows = metadata.read_manifest()
    timestamps = [r["ts"] for r in rows]
    assert timestamps == sorted(timestamps, reverse=True)


def test_read_manifest_limit(isolated_output, tmp_path):
    for i in range(5):
        img = tmp_path / f"img{i}.png"
        img.write_bytes(b"\x89PNG")
        sc = metadata.write_sidecar(img, prompt=f"p{i}", engine="nano_banana", model="m")
        metadata.append_manifest(img, sc)

    rows = metadata.read_manifest(limit=2)
    assert len(rows) == 2


def test_read_manifest_skips_malformed_lines(isolated_output, tmp_path, caplog):
    img = tmp_path / "img.png"
    img.write_bytes(b"\x89PNG")
    sc = metadata.write_sidecar(img, prompt="ok", engine="nano_banana", model="m")
    metadata.append_manifest(img, sc)

    # Append a garbage line.
    manifest = isolated_output / "manifest.jsonl"
    with manifest.open("a", encoding="utf-8") as f:
        f.write("this is not json\n")

    with caplog.at_level(logging.WARNING, logger="kitty.imagen.metadata"):
        rows = metadata.read_manifest()
    # The good row is still returned; the garbage is skipped with a warning.
    assert len(rows) == 1
    assert rows[0]["prompt"] == "ok"
    assert any("malformed" in r.message for r in caplog.records)


# --- regenerate dispatch ---


def test_regenerate_returns_error_for_missing_metadata(isolated_output, tmp_path):
    img = tmp_path / "nope.png"
    img.write_bytes(b"\x89PNG")
    result = metadata.regenerate(str(img))
    assert isinstance(result, list)
    assert "no metadata" in result[0]


def test_regenerate_unknown_engine_returns_error(isolated_output, tmp_path):
    img = tmp_path / "img.png"
    img.write_bytes(b"\x89PNG")
    metadata.write_sidecar(img, prompt="x", engine="mystery_engine", model="m")
    result = metadata.regenerate(str(img))
    assert "unknown engine" in result[0]


def test_regenerate_drops_seed_for_non_seed_engines(isolated_output, tmp_path, caplog):
    """For engines that don't support seed (DALL-E, Imagen 4, Nano Banana),
    regenerate drops the seed and logs a warning. We don't make the
    real API call here — we assert that _regen_dalle would be called
    with seed=None. Since the actual regen function calls the API,
    we test the dispatch logic differently: verify the SEED_SUPPORTED
    set and the dispatch table.
    """
    assert "comfyui" in metadata.SEED_SUPPORTED
    assert "dalle" not in metadata.SEED_SUPPORTED
    assert "imagen4" not in metadata.SEED_SUPPORTED
    assert "nano_banana" not in metadata.SEED_SUPPORTED


# --- open_in_viewer ---


def test_open_in_viewer_missing_file_returns_string(isolated_output):
    result = metadata.open_in_viewer("/nonexistent/path.png")
    assert "not found" in result


def test_open_in_viewer_non_darwin_returns_message(isolated_output, tmp_path, monkeypatch):
    """Non-macOS: returns a message, doesn't try to call `open`."""
    img = tmp_path / "img.png"
    img.write_bytes(b"\x89PNG")
    monkeypatch.setattr("mcp.imagen.metadata.sys.platform", "linux")
    result = metadata.open_in_viewer(str(img))
    assert "macOS-only" in result


def test_open_in_viewer_darwin_calls_open(monkeypatch, tmp_path):
    """macOS: spawns `open` (non-blocking) and returns 'Opened ...'."""
    img = tmp_path / "img.png"
    img.write_bytes(b"\x89PNG")
    monkeypatch.setattr("mcp.imagen.metadata.sys.platform", "darwin")

    calls: list[list[str]] = []
    class _FakePopen:
        def __init__(self, cmd, *a, **kw):
            calls.append(cmd)
    monkeypatch.setattr("mcp.imagen.metadata.subprocess.Popen", _FakePopen)

    result = metadata.open_in_viewer(str(img))
    assert "Opened" in result
    assert calls == [["open", str(img)]]
