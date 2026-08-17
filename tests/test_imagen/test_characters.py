"""Tests for private character reference discovery and curation."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


def _image(path: Path, size=(640, 800), color=(40, 80, 120)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)


def test_source_dir_prefers_private_store(tmp_path, monkeypatch):
    from mcp.imagen.characters import character_source_dir

    root = tmp_path / "faces"
    (root / "james").mkdir(parents=True)
    monkeypatch.setenv("KITTY_FACES_DIR", str(root))
    assert character_source_dir("James") == root / "james"


def test_reference_images_prefer_curated(tmp_path, monkeypatch):
    from mcp.imagen.characters import reference_images

    root = tmp_path / "faces"
    source = root / "james"
    _image(source / "raw.jpg")
    _image(source / "curated" / "clean.jpg")
    monkeypatch.setenv("KITTY_FACES_DIR", str(root))

    refs = reference_images("james")
    assert [p.name for p in refs] == ["clean.jpg"]


def test_curator_excludes_ai_names_duplicates_and_tiny_images(tmp_path):
    from mcp.imagen.characters import curate_references

    source = tmp_path / "source"
    output = tmp_path / "curated"
    _image(source / "good-a.jpg", color=(1, 2, 3))
    _image(source / "good-b.jpg", color=(4, 5, 6))
    _image(source / "Gemini_Generated_Image_fake.png")
    _image(source / "tiny.jpg", size=(120, 400))
    (source / "duplicate.jpg").write_bytes((source / "good-a.jpg").read_bytes())

    report = curate_references(source, output, min_dimension=256, max_dimension=1024)

    assert report["included_count"] == 2
    assert report["excluded_count"] == 3
    reasons = {row["source"]: row["reason"] for row in report["files"]}
    assert reasons["Gemini_Generated_Image_fake.png"] == "ai_generated_filename"
    assert reasons["tiny.jpg"] == "below_min_dimension"
    assert reasons["duplicate.jpg"] == "duplicate_exact_file"
    assert len(list(output.glob("*.jpg"))) == 2


def test_curator_writes_manifest_and_preserves_original(tmp_path):
    from mcp.imagen.characters import curate_references

    source = tmp_path / "source"
    output = tmp_path / "curated"
    original = source / "portrait.png"
    _image(original, size=(1800, 1200))
    before = original.read_bytes()

    report = curate_references(source, output, min_dimension=256, max_dimension=1024)
    manifest = json.loads((output / "manifest.json").read_text())

    assert original.read_bytes() == before
    assert manifest["included_count"] == report["included_count"] == 1
    curated = next(output.glob("*.jpg"))
    with Image.open(curated) as image:
        assert max(image.size) == 1024
        assert image.mode == "RGB"
