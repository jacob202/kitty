"""Tests for mcp/imagen/verify.py — score logic and generate_until loop."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from mcp.imagen.config import settings

# ---------------------------------------------------------------------------
# Mechanical scorer
# ---------------------------------------------------------------------------


def test_score_mechanical_passes():
    from mcp.imagen.verify import score_mechanical

    cfg = {"min_size_bytes": 100}
    score = score_mechanical(b"x" * 500, cfg)
    assert score == 1.0


def test_score_mechanical_with_dimensions():
    from mcp.imagen.verify import score_mechanical

    cfg = {"min_width": 1, "min_height": 1, "min_size_bytes": 0, "reject_blank": False}
    score = score_mechanical(b"x" * 500, cfg)
    assert score == 1.0


def test_score_mechanical_no_cfg():
    from mcp.imagen.verify import score_mechanical

    assert score_mechanical(b"data", None) == 1.0


def test_score_mechanical_too_small():
    from mcp.imagen.verify import score_mechanical

    cfg = {"min_size_bytes": 1000}
    assert score_mechanical(b"x", cfg) == 0.0


def test_score_mechanical_too_large():
    from mcp.imagen.verify import score_mechanical

    cfg = {"max_size_bytes": 50}
    assert score_mechanical(b"x" * 100, cfg) == 0.0


# ---------------------------------------------------------------------------
# Face match scorer — optional dependency guard
# ---------------------------------------------------------------------------


def test_face_match_no_cfg():
    from mcp.imagen.verify import score_face_match

    assert score_face_match(b"test", None) == 1.0


def test_face_match_no_ref_dir():
    from mcp.imagen.verify import score_face_match

    cfg = {"character": "nobody", "threshold": 0.6}
    assert score_face_match(b"test", cfg) == 1.0


def test_face_match_import_error_falls_back():
    from mcp.imagen.verify import score_face_match

    cfg = {"character": "nobody", "threshold": 0.6}
    ref_dir = settings.faces_dir / "nobody"
    ref_dir.mkdir(parents=True, exist_ok=True)
    (ref_dir / "ref.png").write_bytes(b"fake-png")

    with patch("mcp.imagen.verify.log.warning") as mock_warn:
        result = score_face_match(b"not-a-real-png", cfg)
        assert result == 1.0
        mock_warn.assert_called_once()


# ---------------------------------------------------------------------------
# Vision rubric scorer
# ---------------------------------------------------------------------------


def test_vision_rubric_empty():
    from mcp.imagen.verify import score_vision_rubric

    score, details = score_vision_rubric(b"test", [], "prompt")
    assert score == 1.0
    assert details == []


def test_vision_rubric_unavailable_fallback():
    from mcp.imagen.verify import score_vision_rubric

    entries = [{"text": "anatomy is correct"}]
    with patch("mcp.imagen.verify._ollama_vision", side_effect=Exception("no VLM")):
        score, details = score_vision_rubric(b"test", entries, "prompt")
    assert score == 0.5
    assert "unavailable" in details[0]


def test_parse_rubric_response_all_yes():
    from mcp.imagen.verify import _parse_rubric_response

    entries = [{"text": "anatomy ok"}, {"text": "hands ok"}]
    score, fails = _parse_rubric_response("YES\nYES", entries)
    assert score == 1.0
    assert fails == []


def test_parse_rubric_response_some_no():
    from mcp.imagen.verify import _parse_rubric_response

    entries = [{"text": "anatomy ok", "hard": True}, {"text": "hands ok"}]
    score, fails = _parse_rubric_response("NO\nYES", entries)
    assert score == 0.5
    assert len(fails) == 1
    assert "HARD FAIL" in fails[0]


# ---------------------------------------------------------------------------
# Criteria loader
# ---------------------------------------------------------------------------


def test_load_criteria_missing_returns_default():
    from mcp.imagen.verify import load_criteria

    criteria = load_criteria("nonexistent")
    assert criteria.name == "nonexistent"
    assert criteria.face_match is None
    assert criteria.rubric == []
    assert criteria.mechanical is None


def test_load_criteria_from_file(tmp_path):
    from mcp.imagen.verify import load_criteria

    criteria_dir = settings.faces_dir.parent / "criteria"
    criteria_dir.mkdir(parents=True, exist_ok=True)
    file_path = criteria_dir / "test-char.json"
    file_path.write_text(
        json.dumps({
            "face_match": {"character": "jace", "threshold": 0.6},
            "rubric": ["anatomy correct", "good lighting"],
            "mechanical": {"min_width": 512},
        })
    )

    criteria = load_criteria("test-char")
    assert criteria.name == "test-char"
    assert criteria.face_match == {"character": "jace", "threshold": 0.6}
    assert len(criteria.rubric) == 2
    assert criteria.mechanical == {"min_width": 512}


def test_load_criteria_rubric_dicts(tmp_path):
    from mcp.imagen.verify import load_criteria

    criteria_dir = settings.faces_dir.parent / "criteria"
    criteria_dir.mkdir(parents=True, exist_ok=True)
    file_path = criteria_dir / "hard-gate.json"
    file_path.write_text(
        json.dumps({
            "rubric": [{"text": "no artifacts", "hard": True}],
        })
    )

    criteria = load_criteria("hard-gate")
    assert criteria.rubric[0]["hard"] is True


# ---------------------------------------------------------------------------
# Private guard
# ---------------------------------------------------------------------------


def test_private_guard_blocks_cloud():
    from mcp.imagen.verify import _check_private

    with pytest.raises(ValueError, match="private=True"):
        _check_private("nano_banana")
    with pytest.raises(ValueError, match="private=True"):
        _check_private("imagen4")
    with pytest.raises(ValueError, match="private=True"):
        _check_private("dalle")


def test_private_guard_allows_local():
    from mcp.imagen.verify import _check_private

    _check_private("drawthings")
    _check_private("comfyui")


# ---------------------------------------------------------------------------
# Seed source
# ---------------------------------------------------------------------------


def test_seed_source_produces_ints():
    from mcp.imagen.verify import _make_seed_source

    src = _make_seed_source()
    seeds = {src() for _ in range(10)}
    assert all(isinstance(s, int) for s in seeds)
    assert len(seeds) > 1


# ---------------------------------------------------------------------------
# Attempt logging
# ---------------------------------------------------------------------------


def test_log_attempt_writes_jsonl(tmp_path):
    from mcp.imagen.verify import _log_attempt

    log_path = tmp_path / "attempts.jsonl"
    _log_attempt(log_path, 1, 42, {"mechanical": 1.0}, passed=False)
    _log_attempt(log_path, 2, 99, {"mechanical": 1.0, "face_match": 0.8}, passed=True)

    lines = log_path.read_text().strip().split("\n")
    assert len(lines) == 2
    entry = json.loads(lines[0])
    assert entry["attempt"] == 1
    assert entry["seed"] == 42
    assert entry["passed"] is False

    entry2 = json.loads(lines[1])
    assert entry2["attempt"] == 2
    assert entry2["passed"] is True


# ---------------------------------------------------------------------------
# generate_until loop — mocked engine and scorers
# ---------------------------------------------------------------------------


def test_generate_until_returns_results():
    from mcp.imagen.verify import generate_until

    mock_eng = MagicMock()
    mock_eng.generate.return_value = b"fake-image-data"
    mock_eng.name = "drawthings"
    mock_eng.model_name = "test"

    with (
        patch("mcp.imagen.verify.engines.get", return_value=mock_eng),
        patch("mcp.imagen.verify.load_criteria") as mock_criteria,
        patch("mcp.imagen.verify.score_mechanical", return_value=1.0),
        patch("mcp.imagen.verify.score_face_match", return_value=1.0),
        patch("mcp.imagen.verify.score_vision_rubric", return_value=(1.0, [])),
    ):
        mock_criteria.return_value.face_match = None
        mock_criteria.return_value.rubric = []
        mock_criteria.return_value.mechanical = None

        results = generate_until(
            prompt="test prompt",
            criteria_name="test",
            engine="drawthings",
            max_attempts=3,
            keep=2,
        )

    assert len(results) >= 1
    assert results[0]["passed"] is True
    assert results[0]["image_data"] == b"fake-image-data"


def test_generate_until_stops_early_on_pass():
    from mcp.imagen.verify import generate_until

    mock_eng = MagicMock()
    mock_eng.generate.return_value = b"image-data"

    call_count = 0

    def scoring(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return 1.0, []

    with (
        patch("mcp.imagen.verify.engines.get", return_value=mock_eng),
        patch("mcp.imagen.verify.load_criteria") as mock_criteria,
        patch("mcp.imagen.verify.score_mechanical", return_value=1.0),
        patch("mcp.imagen.verify.score_face_match", return_value=1.0),
        patch("mcp.imagen.verify.score_vision_rubric", side_effect=scoring),
    ):
        mock_criteria.return_value.face_match = None
        mock_criteria.return_value.rubric = [{"text": "test", "hard": True}]
        mock_criteria.return_value.mechanical = None

        generate_until("test", "test", engine="drawthings", max_attempts=10, keep=3)

    assert call_count == 1


def test_generate_until_private_guard():
    from mcp.imagen.verify import generate_until

    with patch("mcp.imagen.verify.load_criteria"):
        with pytest.raises(ValueError, match="private=True"):
            generate_until(
                prompt="test",
                criteria_name="test",
                engine="nano_banana",
                private=True,
            )


def test_generate_until_mechanical_fail_skips_other_scores():
    from mcp.imagen.verify import generate_until

    mock_eng = MagicMock()
    mock_eng.generate.return_value = b"small"
    mock_eng.name = "drawthings"

    face_calls = []

    def face_score(*args, **kwargs):
        face_calls.append(1)
        return 1.0

    with (
        patch("mcp.imagen.verify.engines.get", return_value=mock_eng),
        patch("mcp.imagen.verify.load_criteria") as mock_criteria,
        patch("mcp.imagen.verify.score_mechanical", return_value=0.0),
        patch("mcp.imagen.verify.score_face_match", side_effect=face_score),
    ):
        mock_criteria.return_value.face_match = {"character": "x", "threshold": 0.6}
        mock_criteria.return_value.rubric = []
        mock_criteria.return_value.mechanical = {"min_size_bytes": 999999}

        generate_until("test", "test", engine="drawthings", max_attempts=2, keep=1)

    assert len(face_calls) == 0
