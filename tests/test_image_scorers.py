from __future__ import annotations

import httpx
import pytest
from PIL import Image

from gateway.image_evaluation import EvaluationUnavailable


def _gradient_png(path, *, width: int = 512, height: int = 512) -> None:
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    assert pixels is not None
    for y in range(height):
        for x in range(width):
            pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
    image.save(path, format="PNG")


def _mock_ollama_tags(monkeypatch, scorers, *, digest: str = "sha256:abc123") -> None:
    class TagsResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "models": [
                    {
                        "name": "qwen2.5-vl:7b",
                        "model": "qwen2.5-vl:7b",
                        "digest": digest,
                    }
                ]
            }

    monkeypatch.setattr(scorers.httpx, "get", lambda *args, **kwargs: TagsResponse())


def test_mechanics_scorer_returns_versioned_structured_evidence(tmp_path) -> None:
    from gateway.image_scorers import mechanics_scorer

    path = tmp_path / "candidate.png"
    _gradient_png(path)

    result = mechanics_scorer(str(path))

    assert result.passed is True
    assert result.version == "mechanics-pil@1"
    assert result.score["width"] == 512
    assert result.score["height"] == 512
    assert result.score["blank"] is False


def test_mechanics_scorer_fails_closed_on_undecodable_image(tmp_path) -> None:
    from gateway.image_scorers import mechanics_scorer

    path = tmp_path / "candidate.png"
    path.write_bytes(b"not-an-image")

    with pytest.raises(EvaluationUnavailable, match="decode"):
        mechanics_scorer(str(path))


def test_mechanics_scorer_rejects_blank_or_too_small_image(tmp_path) -> None:
    from gateway.image_scorers import mechanics_scorer

    blank = tmp_path / "blank.png"
    Image.new("RGB", (512, 512), "white").save(blank)
    small = tmp_path / "small.png"
    _gradient_png(small, width=128, height=128)

    blank_result = mechanics_scorer(str(blank))
    small_result = mechanics_scorer(str(small))

    assert blank_result.passed is False
    assert "mechanics_blank" in blank_result.labels
    assert small_result.passed is False
    assert "mechanics_too_small" in small_result.labels


def test_identity_scorer_fails_closed_when_face_backend_unavailable(tmp_path, monkeypatch) -> None:
    import gateway.image_scorers as scorers
    from mcp.imagen.face_match import FaceScorerUnavailable

    reference = tmp_path / "reference.png"
    candidate = tmp_path / "candidate.png"
    _gradient_png(reference)
    _gradient_png(candidate)

    class UnavailableMatcher:
        def __init__(self, _path):
            pass

        def score(self, _data):
            raise FaceScorerUnavailable("insightface is not installed")

    monkeypatch.setattr(scorers, "FaceMatcher", UnavailableMatcher)
    scorer = scorers.make_identity_scorer(str(reference))

    with pytest.raises(EvaluationUnavailable, match="identity scorer unavailable"):
        scorer(str(candidate))


def test_identity_scorer_returns_similarity_and_version(tmp_path, monkeypatch) -> None:
    import gateway.image_scorers as scorers
    from mcp.imagen.face_match import FaceScore

    reference = tmp_path / "reference.png"
    candidate = tmp_path / "candidate.png"
    _gradient_png(reference)
    _gradient_png(candidate)

    class FakeMatcher:
        def __init__(self, path):
            assert str(path) == str(reference)

        def score(self, _data):
            return FaceScore(similarity=0.71, reference_faces=1, candidate_faces=1)

    monkeypatch.setattr(scorers, "FaceMatcher", FakeMatcher)
    scorer = scorers.make_identity_scorer(str(reference), threshold=0.55)
    result = scorer(str(candidate))

    assert result.passed is True
    assert result.score["similarity"] == pytest.approx(0.71)
    assert result.score["threshold"] == pytest.approx(0.55)
    assert result.version == "identity-insightface-buffalo_l@1"


def test_ollama_rubric_scorer_requires_pinned_model_revision() -> None:
    from gateway.image_scorers import make_ollama_rubric_scorer

    with pytest.raises(EvaluationUnavailable, match="model revision"):
        make_ollama_rubric_scorer(
            dimension="photorealism",
            prompt="adult male portrait",
            rubric="looks like a real photograph",
            model="qwen2.5-vl:7b",
            model_revision="",
        )


def test_ollama_rubric_scorer_is_strict_and_versioned(tmp_path, monkeypatch) -> None:
    import gateway.image_scorers as scorers

    candidate = tmp_path / "candidate.png"
    _gradient_png(candidate)

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"response": "YES"}

    _mock_ollama_tags(monkeypatch, scorers)
    monkeypatch.setattr(scorers.httpx, "post", lambda *args, **kwargs: Response())
    scorer = scorers.make_ollama_rubric_scorer(
        dimension="photorealism",
        prompt="adult male portrait",
        rubric="looks like a real photograph rather than CGI or illustration",
        model="qwen2.5-vl:7b",
        model_revision="sha256:abc123",
    )
    result = scorer(str(candidate))

    assert result.passed is True
    assert result.score == 1.0
    assert result.version == "ollama-rubric@1:qwen2.5-vl:7b@sha256:abc123"


def test_ollama_rubric_scorer_fails_closed_when_local_vlm_unavailable(
    tmp_path, monkeypatch
) -> None:
    import gateway.image_scorers as scorers

    candidate = tmp_path / "candidate.png"
    _gradient_png(candidate)

    def unavailable(*_args, **_kwargs):
        request = httpx.Request("POST", "http://127.0.0.1:11434/api/generate")
        raise httpx.ConnectError("offline", request=request)

    _mock_ollama_tags(monkeypatch, scorers)
    monkeypatch.setattr(scorers.httpx, "post", unavailable)
    scorer = scorers.make_ollama_rubric_scorer(
        dimension="anatomy",
        prompt="full body adult male",
        rubric="human anatomy is coherent",
        model="qwen2.5-vl:7b",
        model_revision="sha256:abc123",
    )

    with pytest.raises(EvaluationUnavailable, match="local VLM"):
        scorer(str(candidate))


def test_ollama_rubric_scorer_rejects_ambiguous_model_answer(tmp_path, monkeypatch) -> None:
    import gateway.image_scorers as scorers

    candidate = tmp_path / "candidate.png"
    _gradient_png(candidate)

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": "probably"}

    _mock_ollama_tags(monkeypatch, scorers)
    monkeypatch.setattr(scorers.httpx, "post", lambda *args, **kwargs: Response())
    scorer = scorers.make_ollama_rubric_scorer(
        dimension="composition",
        prompt="two subjects",
        rubric="composition is coherent",
        model="qwen2.5-vl:7b",
        model_revision="sha256:abc123",
    )

    with pytest.raises(EvaluationUnavailable, match="strict YES or NO"):
        scorer(str(candidate))


def test_ollama_rubric_scorer_refuses_nonlocal_endpoint() -> None:
    from gateway.image_scorers import make_ollama_rubric_scorer

    with pytest.raises(EvaluationUnavailable, match="loopback-only"):
        make_ollama_rubric_scorer(
            dimension="photorealism",
            prompt="adult male portrait",
            rubric="looks photographic",
            model="qwen2.5-vl:7b",
            model_revision="sha256:abc123",
            base_url="https://example.com",
        )


def test_build_imagebench_scorers_leaves_unavailable_required_scorers_missing(tmp_path) -> None:
    from gateway.image_evaluation import evaluate_image
    from gateway.image_scorers import build_imagebench_scorers

    candidate = tmp_path / "candidate.png"
    _gradient_png(candidate)
    scorers = build_imagebench_scorers(
        required_scorers=["mechanics", "photorealism"],
        prompt="adult male portrait in natural daylight",
    )

    assert set(scorers) == {"mechanics"}
    with pytest.raises(EvaluationUnavailable, match="photorealism"):
        evaluate_image(
            image_path=str(candidate),
            required_scorers=["mechanics", "photorealism"],
            scorers=scorers,
        )


def test_build_imagebench_scorers_wires_vlm_dimension_when_pinned() -> None:
    from gateway.image_scorers import build_imagebench_scorers

    scorers = build_imagebench_scorers(
        required_scorers=["mechanics", "photorealism", "anatomy"],
        prompt="full body adult male photograph",
        vlm_model="qwen2.5-vl:7b",
        vlm_model_revision="sha256:abc123",
    )

    assert set(scorers) == {"mechanics", "photorealism", "anatomy"}


def test_build_imagebench_scorers_requires_reference_for_identity(tmp_path) -> None:
    from gateway.image_scorers import build_imagebench_scorers

    without_ref = build_imagebench_scorers(
        required_scorers=["mechanics", "identity"],
        prompt="same authorized adult male identity",
    )
    assert set(without_ref) == {"mechanics"}

    reference = tmp_path / "reference.png"
    _gradient_png(reference)
    with_ref = build_imagebench_scorers(
        required_scorers=["mechanics", "identity"],
        prompt="same authorized adult male identity",
        identity_reference_path=str(reference),
    )
    assert set(with_ref) == {"mechanics", "identity"}


def test_build_imagebench_scorers_requires_auxiliary_reference_for_comparison_dimension() -> None:
    from gateway.image_scorers import build_imagebench_scorers

    scorers = build_imagebench_scorers(
        required_scorers=["mechanics", "reference_role"],
        prompt="use pose reference without identity leakage",
        vlm_model="qwen2.5-vl:7b",
        vlm_model_revision="sha256:abc123",
    )
    assert set(scorers) == {"mechanics"}


def test_ollama_rubric_scorer_rejects_loaded_model_revision_mismatch(tmp_path, monkeypatch) -> None:
    import gateway.image_scorers as scorers

    candidate = tmp_path / "candidate.png"
    _gradient_png(candidate)

    class TagsResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "models": [
                    {
                        "name": "qwen2.5-vl:7b",
                        "model": "qwen2.5-vl:7b",
                        "digest": "sha256:different",
                    }
                ]
            }

    monkeypatch.setattr(scorers.httpx, "get", lambda *args, **kwargs: TagsResponse())
    scorer = scorers.make_ollama_rubric_scorer(
        dimension="photorealism",
        prompt="adult male portrait",
        rubric="looks photographic",
        model="qwen2.5-vl:7b",
        model_revision="sha256:expected",
    )

    with pytest.raises(EvaluationUnavailable, match="revision mismatch"):
        scorer(str(candidate))


def test_assignment_dimension_is_not_owned_by_generic_vlm_adapter(tmp_path) -> None:
    from gateway.image_scorers import build_imagebench_scorers

    reference = tmp_path / "reference.png"
    _gradient_png(reference)
    scorers = build_imagebench_scorers(
        required_scorers=["mechanics", "assignment"],
        prompt="two distinct authorized adult male identities side by side",
        auxiliary_image_paths=[str(reference)],
        vlm_model="qwen2.5-vl:7b",
        vlm_model_revision="sha256:abc123",
    )

    # PR #611 owns assignment through gateway.image_identity_assignment and
    # requires structured detection/similarity evidence; a generic VLM must
    # never masquerade as that canonical assignment scorer.
    assert set(scorers) == {"mechanics"}
