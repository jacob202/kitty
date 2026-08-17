"""Tests for the fixed, fail-closed character benchmark."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_benchmark_has_ten_fixed_unique_scenes():
    from mcp.imagen.benchmark import BENCHMARK_SCENES

    assert len(BENCHMARK_SCENES) == 10
    assert len({scene.id for scene in BENCHMARK_SCENES}) == 10
    assert any("shirtless" in scene.prompt.lower() for scene in BENCHMARK_SCENES)
    assert any("full-body" in scene.prompt.lower() for scene in BENCHMARK_SCENES)


def _criteria():
    criteria = MagicMock()
    criteria.face_match = {"character": "james", "threshold": 0.55}
    criteria.rubric = [{"text": "photorealistic", "hard": True}]
    criteria.mechanical = {"min_width": 512, "min_height": 512}
    return criteria


def test_automated_pass_is_not_final_pass(tmp_path: Path):
    from mcp.imagen.benchmark import run_character_benchmark

    ref = tmp_path / "ref.jpg"
    ref.write_bytes(b"ref")
    engine = MagicMock()
    engine.generate.return_value = b"generated"

    with (
        patch("mcp.imagen.benchmark.engines.get", return_value=engine),
        patch("mcp.imagen.benchmark.reference_images", return_value=[ref]),
        patch("mcp.imagen.benchmark.select_identity_reference", return_value=ref),
        patch("mcp.imagen.benchmark.load_criteria", return_value=_criteria()),
        patch("mcp.imagen.benchmark.score_mechanical", return_value=1.0),
        patch("mcp.imagen.benchmark.score_face_match", return_value=0.60),
        patch("mcp.imagen.benchmark.score_vision_rubric", return_value=(1.0, [])),
    ):
        report = run_character_benchmark("james", output_root=tmp_path / "runs")

    assert report["verdict"] == "NEEDS_ADVERSARIAL_REVIEW"
    assert report["automated_checks_passed"] is True
    assert len(report["scenes"]) == 10
    assert all(Path(row["image_path"]).parent.name == "quarantine" for row in report["scenes"])
    assert Path(report["report_path"]).exists()


def test_face_floor_failure_is_fail(tmp_path: Path):
    from mcp.imagen.benchmark import run_character_benchmark

    ref = tmp_path / "ref.jpg"
    ref.write_bytes(b"ref")
    engine = MagicMock()
    engine.generate.return_value = b"generated"
    scores = iter([0.60] * 9 + [0.40])

    with (
        patch("mcp.imagen.benchmark.engines.get", return_value=engine),
        patch("mcp.imagen.benchmark.reference_images", return_value=[ref]),
        patch("mcp.imagen.benchmark.select_identity_reference", return_value=ref),
        patch("mcp.imagen.benchmark.load_criteria", return_value=_criteria()),
        patch("mcp.imagen.benchmark.score_mechanical", return_value=1.0),
        patch("mcp.imagen.benchmark.score_face_match", side_effect=lambda *a, **k: next(scores)),
        patch("mcp.imagen.benchmark.score_vision_rubric", return_value=(1.0, [])),
    ):
        report = run_character_benchmark("james", output_root=tmp_path / "runs")

    assert report["verdict"] == "FAIL"
    assert report["face_min"] == 0.40


def test_verifier_unavailable_blocks_instead_of_passing(tmp_path: Path):
    from mcp.imagen.benchmark import run_character_benchmark
    from mcp.imagen.verify import VerifierUnavailable

    ref = tmp_path / "ref.jpg"
    ref.write_bytes(b"ref")
    engine = MagicMock()
    engine.generate.return_value = b"generated"

    with (
        patch("mcp.imagen.benchmark.engines.get", return_value=engine),
        patch("mcp.imagen.benchmark.reference_images", return_value=[ref]),
        patch("mcp.imagen.benchmark.select_identity_reference", return_value=ref),
        patch("mcp.imagen.benchmark.load_criteria", return_value=_criteria()),
        patch("mcp.imagen.benchmark.score_mechanical", return_value=1.0),
        patch("mcp.imagen.benchmark.score_face_match", side_effect=VerifierUnavailable("no insightface")),
    ):
        report = run_character_benchmark("james", output_root=tmp_path / "runs")

    assert report["verdict"] == "BLOCKED"
    assert report["automated_checks_passed"] is False
    assert "no insightface" in report["blocker"]
