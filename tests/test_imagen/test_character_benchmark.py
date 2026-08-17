"""Tests for mcp/imagen/benchmark.py — the face-locked 10-scene benchmark."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mcp.imagen.character_lock import create_lock
from mcp.imagen.config import settings
from mcp.imagen.engines.base import RefusalError
from mcp.imagen.face_match import FaceScorerUnavailable


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "character_locks_dir", tmp_path / "locks")
    monkeypatch.setattr(settings, "output_dir", tmp_path / "output")


def _make_png(path, pixel=(10, 20, 30), size=(8, 8)):
    from PIL import Image

    Image.new("RGB", size, pixel).save(path, format="PNG")


def _lock_james(tmp_path):
    photo = tmp_path / "james.png"
    _make_png(photo)
    return create_lock("james", photo)


def test_scene_count_is_ten():
    from mcp.imagen.benchmark import SCENES

    assert len(SCENES) == 10
    assert len({s["name"] for s in SCENES}) == 10


def test_no_body_hair_or_shirtless_scenes():
    from mcp.imagen.benchmark import SCENES

    banned = ("shirtless", "body hair", "topless", "nude", "naked")
    for scene in SCENES:
        text = scene["prompt"].lower()
        for word in banned:
            assert word not in text


def test_missing_lock_blocks_whole_run(tmp_path):
    from mcp.imagen.benchmark import run_character_benchmark

    report = run_character_benchmark("james", engine_name="runware")
    assert report.automated_verdict == "BLOCKED"
    assert report.scenes[0].result == "BLOCKED"


def test_unknown_engine_blocks(tmp_path):
    from mcp.imagen.benchmark import run_character_benchmark

    _lock_james(tmp_path)
    report = run_character_benchmark("james", engine_name="does-not-exist")
    assert report.automated_verdict == "BLOCKED"


def test_face_scorer_unavailable_blocks_before_generating(tmp_path):
    from mcp.imagen.benchmark import run_character_benchmark

    _lock_james(tmp_path)
    mock_eng = MagicMock()

    with (
        patch("mcp.imagen.benchmark.engines.get", return_value=mock_eng),
        patch(
            "mcp.imagen.benchmark.FaceMatcher.ensure_ready",
            side_effect=FaceScorerUnavailable("insightface is not installed"),
        ),
    ):
        report = run_character_benchmark("james", engine_name="runware")

    assert report.automated_verdict == "BLOCKED"
    mock_eng.generate.assert_not_called()


def test_every_generation_uses_exactly_the_locked_reference(tmp_path):
    from mcp.imagen.benchmark import run_character_benchmark

    locked = _lock_james(tmp_path)
    mock_eng = MagicMock()
    mock_eng.generate.return_value = _fake_png_bytes()

    with (
        patch("mcp.imagen.benchmark.engines.get", return_value=mock_eng),
        patch("mcp.imagen.benchmark.FaceMatcher.ensure_ready", return_value=None),
        patch("mcp.imagen.benchmark.FaceMatcher.score", return_value=_fake_face_score(0.9)),
    ):
        run_character_benchmark("james", engine_name="runware")

    assert mock_eng.generate.call_count == 10
    for call in mock_eng.generate.call_args_list:
        assert call.kwargs["identity_images"] == [locked.path]


def test_pass_automated_when_all_scenes_pass(tmp_path):
    from mcp.imagen.benchmark import run_character_benchmark

    _lock_james(tmp_path)
    mock_eng = MagicMock()
    mock_eng.generate.return_value = _fake_png_bytes()

    with (
        patch("mcp.imagen.benchmark.engines.get", return_value=mock_eng),
        patch("mcp.imagen.benchmark.FaceMatcher.ensure_ready", return_value=None),
        patch("mcp.imagen.benchmark.FaceMatcher.score", return_value=_fake_face_score(0.9)),
    ):
        report = run_character_benchmark("james", engine_name="runware")

    assert report.automated_verdict == "PASS_AUTOMATED"
    assert report.final_review_required is True
    assert len(report.scenes) == 10
    assert all(s.result == "PASS_AUTOMATED" for s in report.scenes)


def test_fail_when_face_score_below_threshold(tmp_path):
    from mcp.imagen.benchmark import run_character_benchmark

    _lock_james(tmp_path)
    mock_eng = MagicMock()
    mock_eng.generate.return_value = _fake_png_bytes()

    with (
        patch("mcp.imagen.benchmark.engines.get", return_value=mock_eng),
        patch("mcp.imagen.benchmark.FaceMatcher.ensure_ready", return_value=None),
        patch("mcp.imagen.benchmark.FaceMatcher.score", return_value=_fake_face_score(0.05)),
    ):
        report = run_character_benchmark("james", engine_name="runware")

    assert report.automated_verdict == "FAIL"
    assert all(s.result == "FAIL" for s in report.scenes)


def test_refusal_marks_scene_fail_not_block(tmp_path):
    from mcp.imagen.benchmark import run_character_benchmark

    _lock_james(tmp_path)
    mock_eng = MagicMock()
    mock_eng.generate.side_effect = RefusalError("blocked by safety filter")

    with (
        patch("mcp.imagen.benchmark.engines.get", return_value=mock_eng),
        patch("mcp.imagen.benchmark.FaceMatcher.ensure_ready", return_value=None),
    ):
        report = run_character_benchmark("james", engine_name="runware")

    assert report.automated_verdict == "FAIL"
    assert all(s.result == "FAIL" for s in report.scenes)
    assert "refused" in report.scenes[0].error


def test_unexpected_engine_error_blocks_that_scene(tmp_path):
    from mcp.imagen.benchmark import run_character_benchmark

    _lock_james(tmp_path)
    mock_eng = MagicMock()
    mock_eng.generate.side_effect = RuntimeError("no valid rotated RUNWARE_API_KEY")

    with (
        patch("mcp.imagen.benchmark.engines.get", return_value=mock_eng),
        patch("mcp.imagen.benchmark.FaceMatcher.ensure_ready", return_value=None),
    ):
        report = run_character_benchmark("james", engine_name="runware")

    assert report.automated_verdict == "BLOCKED"
    assert all(s.result == "BLOCKED" for s in report.scenes)


def test_outputs_are_quarantined_and_report_written(tmp_path):
    from mcp.imagen.benchmark import run_character_benchmark

    _lock_james(tmp_path)
    mock_eng = MagicMock()
    mock_eng.generate.return_value = _fake_png_bytes()

    with (
        patch("mcp.imagen.benchmark.engines.get", return_value=mock_eng),
        patch("mcp.imagen.benchmark.FaceMatcher.ensure_ready", return_value=None),
        patch("mcp.imagen.benchmark.FaceMatcher.score", return_value=_fake_face_score(0.9)),
    ):
        report = run_character_benchmark("james", engine_name="runware")

    from pathlib import Path

    qdir = Path(report.quarantine_dir)
    assert qdir.exists()
    assert (qdir / "report.json").exists()
    saved = list(qdir.glob("*.png"))
    assert len(saved) == 10


def _fake_png_bytes() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (512, 512), (5, 6, 7)).save(buf, format="PNG")
    return buf.getvalue()


def _fake_face_score(similarity: float):
    from mcp.imagen.face_match import FaceScore

    return FaceScore(similarity=similarity, reference_faces=1, candidate_faces=1)
