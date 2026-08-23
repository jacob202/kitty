"""Tests for mcp/imagen/face_match.py — exact single-reference face scoring."""
from __future__ import annotations

import importlib.util
from pathlib import Path

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


class _FakeMultiFaceBackend:
    def __init__(self, reference_embeddings, detections):
        self.reference_embeddings = reference_embeddings
        self.detections = detections
        self.reference_calls = []
        self.detect_calls = 0

    def embed_reference(self, path):
        self.reference_calls.append(str(path))
        return self.reference_embeddings[str(path)]

    def detect(self, image_data):
        self.detect_calls += 1
        assert image_data == b"candidate"
        return list(self.detections)


def test_multiface_builds_all_reference_matrix_and_character_assignment(tmp_path):
    from mcp.imagen.face_match import (
        CharacterFaceReference,
        FaceDetection,
        MultiFaceMatcher,
    )

    a1 = tmp_path / "a1.png"
    a2 = tmp_path / "a2.png"
    b1 = tmp_path / "b1.png"
    b2 = tmp_path / "b2.png"
    refs = [
        CharacterFaceReference("subject_1", "char_a", a1, position="left"),
        CharacterFaceReference("subject_1", "char_a", a2, position="left"),
        CharacterFaceReference("subject_2", "char_b", b1, position="right"),
        CharacterFaceReference("subject_2", "char_b", b2, position="right"),
    ]
    backend = _FakeMultiFaceBackend(
        {
            str(a1): [1.0, 0.0],
            str(a2): [0.9, 0.1],
            str(b1): [0.0, 1.0],
            str(b2): [0.1, 0.9],
        },
        [
            FaceDetection("face_right", (80.0, 0.0, 100.0, 20.0), [0.0, 1.0]),
            FaceDetection("face_left", (0.0, 0.0, 20.0, 20.0), [1.0, 0.0]),
        ],
    )

    evidence = MultiFaceMatcher(refs, backend=backend).score_assignment(b"candidate")

    assert len(evidence.reference_similarity_matrix) == 4
    assert all(len(row) == 2 for row in evidence.reference_similarity_matrix)
    assert evidence.character_ids == ("char_a", "char_b")
    assert evidence.detected[0].center_x == 90.0
    assert evidence.detected[1].center_x == 10.0
    assert evidence.detected_cast_slots == ("subject_2", "subject_1")
    assert evidence.assignment.passed is True
    assert evidence.assignment.labels == []
    assert backend.detect_calls == 1
    assert len(backend.reference_calls) == 4


def test_multiface_detects_identity_swap_against_left_right_geometry(tmp_path):
    from mcp.imagen.face_match import CharacterFaceReference, FaceDetection, MultiFaceMatcher

    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    refs = [
        CharacterFaceReference("subject_1", "char_a", a, position="left"),
        CharacterFaceReference("subject_2", "char_b", b, position="right"),
    ]
    backend = _FakeMultiFaceBackend(
        {str(a): [1.0, 0.0], str(b): [0.0, 1.0]},
        [
            FaceDetection("left_face", (0.0, 0.0, 20.0, 20.0), [0.0, 1.0]),
            FaceDetection("right_face", (80.0, 0.0, 100.0, 20.0), [1.0, 0.0]),
        ],
    )

    evidence = MultiFaceMatcher(refs, backend=backend).score_assignment(b"candidate")

    assert evidence.assignment.passed is False
    assert "identity_swap:subject_1->subject_2" in evidence.assignment.labels
    assert "identity_swap:subject_2->subject_1" in evidence.assignment.labels


def test_multiface_extra_detection_is_structured_assignment_failure(tmp_path):
    from mcp.imagen.face_match import CharacterFaceReference, FaceDetection, MultiFaceMatcher

    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    refs = [
        CharacterFaceReference("subject_1", "char_a", a, position="left"),
        CharacterFaceReference("subject_2", "char_b", b, position="right"),
    ]
    backend = _FakeMultiFaceBackend(
        {str(a): [1.0, 0.0], str(b): [0.0, 1.0]},
        [
            FaceDetection("left", (0.0, 0.0, 20.0, 20.0), [1.0, 0.0]),
            FaceDetection("middle", (40.0, 0.0, 60.0, 20.0), [0.5, 0.5]),
            FaceDetection("right", (80.0, 0.0, 100.0, 20.0), [0.0, 1.0]),
        ],
    )

    evidence = MultiFaceMatcher(refs, backend=backend).score_assignment(b"candidate")
    assert evidence.assignment.passed is False
    assert evidence.assignment.labels == ["unexpected_subjects"]
    assert evidence.detected_cast_slots == ("subject_1", "unassigned_1", "subject_2")


def test_multiface_requires_distinct_left_right_placement_for_two_character_swap_check(tmp_path):
    from mcp.imagen.face_match import (
        CharacterFaceReference,
        FaceDetection,
        FaceScorerUnavailable,
        MultiFaceMatcher,
    )

    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    refs = [
        CharacterFaceReference("subject_1", "char_a", a),
        CharacterFaceReference("subject_2", "char_b", b),
    ]
    backend = _FakeMultiFaceBackend(
        {str(a): [1.0, 0.0], str(b): [0.0, 1.0]},
        [
            FaceDetection("left", (0.0, 0.0, 20.0, 20.0), [1.0, 0.0]),
            FaceDetection("right", (80.0, 0.0, 100.0, 20.0), [0.0, 1.0]),
        ],
    )

    with pytest.raises(FaceScorerUnavailable, match="left/right placement"):
        MultiFaceMatcher(refs, backend=backend).score_assignment(b"candidate")


def test_multiface_default_backend_fails_closed_when_insightface_missing(tmp_path, monkeypatch):
    from mcp.imagen.face_match import (
        CharacterFaceReference,
        FaceScorerUnavailable,
        MultiFaceMatcher,
    )

    ref = tmp_path / "a.png"
    refs = [CharacterFaceReference("subject_1", "char_a", ref, position="left")]
    real_find_spec = importlib.util.find_spec

    def _fake(name):
        if name == "insightface":
            return None
        return real_find_spec(name)

    monkeypatch.setattr("importlib.util.find_spec", _fake)
    with pytest.raises(FaceScorerUnavailable, match="insightface"):
        MultiFaceMatcher(refs).score_assignment(b"candidate")


def test_multiface_missing_reference_file_fails_closed(tmp_path):
    from mcp.imagen.face_match import (
        CharacterFaceReference,
        FaceScorerUnavailable,
        MultiFaceMatcher,
    )

    missing = tmp_path / "missing.png"

    class _Backend:
        def embed_reference(self, path):
            return Path(path).read_bytes()

        def detect(self, image_data):
            return []

    with pytest.raises(FaceScorerUnavailable, match="reference .* unavailable"):
        MultiFaceMatcher(
            [CharacterFaceReference("subject_1", "char_a", missing)],
            backend=_Backend(),
        ).score_assignment(b"candidate")
