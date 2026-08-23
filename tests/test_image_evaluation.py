from __future__ import annotations

import pytest

from gateway.image_evaluation import EvaluationUnavailable, evaluate_image


def test_evaluate_image_refuses_empty_required_scorers() -> None:
    with pytest.raises(EvaluationUnavailable, match="at least one required scorer"):
        evaluate_image(image_path="candidate.png", required_scorers=[], scorers={})


def test_scorer_result_contract_is_explicit() -> None:
    import gateway.image_evaluation as evaluation

    assert hasattr(evaluation, "ScorerResult")


def test_evaluate_image_preserves_explicit_failed_scorer_evidence() -> None:
    from gateway.image_evaluation import ScorerResult

    result = evaluate_image(
        image_path="candidate.png",
        required_scorers=["identity"],
        scorers={
            "identity": lambda _path: ScorerResult(
                passed=False,
                score=0.31,
                version="identity-v2",
                labels=["identity_mismatch"],
            )
        },
    )

    assert result.passed is False
    assert result.dimensions == {"identity": 0.31}
    assert result.scorer_versions == {"identity": "identity-v2"}
    assert result.labels == ["identity_mismatch"]


def test_evaluate_image_rejects_unstructured_scorer_output() -> None:
    with pytest.raises(EvaluationUnavailable, match="structured ScorerResult"):
        evaluate_image(
            image_path="candidate.png",
            required_scorers=["identity"],
            scorers={"identity": lambda _path: 0.92},
        )


def test_evaluate_image_rejects_missing_scorer_version() -> None:
    from gateway.image_evaluation import ScorerResult

    with pytest.raises(EvaluationUnavailable, match="version"):
        evaluate_image(
            image_path="candidate.png",
            required_scorers=["identity"],
            scorers={
                "identity": lambda _path: ScorerResult(
                    passed=True,
                    score=0.92,
                    version="",
                )
            },
        )


def test_evaluate_image_rejects_non_boolean_pass_evidence() -> None:
    from typing import Any, cast

    from gateway.image_evaluation import ScorerResult

    bad_pass = cast(Any, "yes")
    with pytest.raises(EvaluationUnavailable, match="boolean passed"):
        evaluate_image(
            image_path="candidate.png",
            required_scorers=["identity"],
            scorers={
                "identity": lambda _path: ScorerResult(
                    passed=bad_pass,
                    score=0.92,
                    version="identity-v2",
                )
            },
        )

def test_evaluate_image_rejects_malformed_labels() -> None:
    from typing import Any, cast

    from gateway.image_evaluation import ScorerResult

    bad_labels = cast(Any, "identity_mismatch")
    with pytest.raises(EvaluationUnavailable, match="labels"):
        evaluate_image(
            image_path="candidate.png",
            required_scorers=["identity"],
            scorers={
                "identity": lambda _path: ScorerResult(
                    passed=False,
                    score=0.31,
                    version="identity-v2",
                    labels=bad_labels,
                )
            },
        )

def test_evaluate_image_wraps_scorer_exceptions() -> None:
    def broken_scorer(_path: str):
        raise ValueError("scorer internal error")

    with pytest.raises(EvaluationUnavailable, match="identity.*failed") as exc_info:
        evaluate_image(
            image_path="candidate.png",
            required_scorers=["identity"],
            scorers={"identity": broken_scorer},
        )

    assert isinstance(exc_info.value.__cause__, ValueError)


def test_evaluate_image_fails_if_any_required_scorer_fails() -> None:
    from gateway.image_evaluation import ScorerResult

    result = evaluate_image(
        image_path="candidate.png",
        required_scorers=["identity", "anatomy"],
        scorers={
            "identity": lambda _path: ScorerResult(True, 0.93, "identity-v2", ["identity_ok"]),
            "anatomy": lambda _path: ScorerResult(False, 0.41, "anatomy-v1", ["anatomy_fail"]),
        },
    )

    assert result.passed is False
    assert result.dimensions == {"identity": 0.93, "anatomy": 0.41}
    assert result.scorer_versions == {"identity": "identity-v2", "anatomy": "anatomy-v1"}
    assert result.labels == ["identity_ok", "anatomy_fail"]


def test_evaluate_image_rejects_duplicate_required_scorers() -> None:
    from gateway.image_evaluation import ScorerResult

    with pytest.raises(EvaluationUnavailable, match="duplicate required scorers"):
        evaluate_image(
            image_path="candidate.png",
            required_scorers=["identity", "identity"],
            scorers={"identity": lambda _path: ScorerResult(True, 0.93, "identity-v2")},
        )

def test_evaluate_image_rejects_non_string_scorer_version() -> None:
    from typing import Any, cast

    from gateway.image_evaluation import ScorerResult

    bad_version = cast(Any, 123)
    with pytest.raises(EvaluationUnavailable, match="version"):
        evaluate_image(
            image_path="candidate.png",
            required_scorers=["identity"],
            scorers={
                "identity": lambda _path: ScorerResult(
                    passed=True,
                    score=0.92,
                    version=bad_version,
                )
            },
        )
