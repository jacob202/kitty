"""Tests for mcp/imagen/face_match.py — exact single-reference face scoring."""
from __future__ import annotations

import importlib.util

import pytest

_HAS_INSIGHTFACE = importlib.util.find_spec("insightface") is not None and (
    importlib.util.find_spec("cv2") is not None
)


def _make_png(path, pixel=(10, 20, 30), size=(8, 8)):
    from PIL import Image

    Image.new("RGB", size, pixel).save(path, format="PNG")


def test_unavailable_when_insightface_missing(tmp_path, monkeypatch):
    from mcp.imagen.face_match import FaceMatcher, FaceScorerUnavailable

    ref = tmp_path / "ref.png"
    _make_png(ref)

    monkeypatch.setattr(
        "importlib.util.find_spec",
        lambda name: None if name == "insightface" else importlib.util.find_spec(name),
    )

    matcher = FaceMatcher(ref)
    with pytest.raises(FaceScorerUnavailable, match="insightface"):
        matcher.ensure_ready()


def test_unavailable_when_cv2_missing(tmp_path, monkeypatch):
    from mcp.imagen.face_match import FaceMatcher, FaceScorerUnavailable

    ref = tmp_path / "ref.png"
    _make_png(ref)

    real_find_spec = importlib.util.find_spec

    def _fake(name):
        if name == "insightface":
            return real_find_spec("importlib")  # any truthy spec
        if name == "cv2":
            return None
        return real_find_spec(name)

    monkeypatch.setattr("importlib.util.find_spec", _fake)

    matcher = FaceMatcher(ref)
    with pytest.raises(FaceScorerUnavailable, match="opencv"):
        matcher.ensure_ready()


@pytest.mark.skipif(not _HAS_INSIGHTFACE, reason="insightface/opencv not installed")
def test_unavailable_when_reference_undecodable(tmp_path):
    from mcp.imagen.face_match import FaceMatcher, FaceScorerUnavailable

    ref = tmp_path / "not-an-image.png"
    ref.write_bytes(b"not a real png")

    matcher = FaceMatcher(ref)
    with pytest.raises(FaceScorerUnavailable):
        matcher.ensure_ready()


@pytest.mark.skipif(not _HAS_INSIGHTFACE, reason="insightface/opencv not installed")
def test_unavailable_when_no_face_in_reference(tmp_path):
    from mcp.imagen.face_match import FaceMatcher, FaceScorerUnavailable

    ref = tmp_path / "blank.png"
    _make_png(ref)  # solid color square — no detectable face

    matcher = FaceMatcher(ref)
    with pytest.raises(FaceScorerUnavailable, match="no face"):
        matcher.ensure_ready()


@pytest.mark.skipif(not _HAS_INSIGHTFACE, reason="insightface/opencv not installed")
def test_score_no_face_in_candidate_returns_zero(tmp_path, monkeypatch):
    from mcp.imagen.face_match import FaceMatcher

    ref = tmp_path / "ref.png"
    _make_png(ref)

    matcher = FaceMatcher(ref)
    matcher._reference_embedding = [1.0, 0.0, 0.0]

    class _EmptyApp:
        def get(self, img):
            return []

    matcher._app = _EmptyApp()

    from PIL import Image

    candidate_png = tmp_path / "candidate.png"
    Image.new("RGB", (8, 8)).save(candidate_png, format="PNG")

    score = matcher.score(candidate_png.read_bytes())
    assert score.similarity == 0.0
    assert score.candidate_faces == 0


def test_score_before_ready_initializes_once(tmp_path, monkeypatch):
    """ensure_ready() must be idempotent — the model loads at most once."""
    from mcp.imagen.face_match import FaceMatcher

    ref = tmp_path / "ref.png"
    _make_png(ref)

    matcher = FaceMatcher(ref)
    calls = []

    def fake_load():
        calls.append(1)
        matcher._app = object()
        matcher._reference_embedding = [1.0, 0.0]

    monkeypatch.setattr(matcher, "_load", fake_load)
    matcher.ensure_ready()
    matcher.ensure_ready()
    assert len(calls) == 1
