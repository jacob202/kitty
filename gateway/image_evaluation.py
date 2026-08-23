"""Fail-closed Image Lab evaluation contract.

Keeps evaluation separate from generation. A missing required scorer is an
infrastructure failure, never a passing result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


class EvaluationUnavailable(RuntimeError):
    """Raised when a required evaluator is not available."""


@dataclass(frozen=True)
class ScorerResult:
    """Explicit evidence returned by one required image scorer."""

    passed: bool
    score: Any
    version: str
    labels: list[str] = field(default_factory=list)


@dataclass
class EvaluationResult:
    passed: bool
    labels: list[str] = field(default_factory=list)
    dimensions: dict[str, Any] = field(default_factory=dict)
    scorer_versions: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "labels": list(self.labels),
            "dimensions": dict(self.dimensions),
            "scorer_versions": dict(self.scorer_versions),
        }


def evaluate_image(
    *,
    image_path: str,
    required_scorers: list[str],
    scorers: dict[str, Callable[[str], Any]] | None = None,
) -> EvaluationResult:
    """Run registered scorers and fail closed when unavailable."""
    if not required_scorers:
        raise EvaluationUnavailable("at least one required scorer must be configured")
    if len(set(required_scorers)) != len(required_scorers):
        raise EvaluationUnavailable("duplicate required scorers are not allowed")

    available = scorers or {}
    missing = [name for name in required_scorers if name not in available]
    if missing:
        raise EvaluationUnavailable(
            f"required scorers unavailable: {', '.join(sorted(missing))}"
        )

    dimensions: dict[str, Any] = {}
    versions: dict[str, str] = {}
    labels: list[str] = []
    passed = True
    for name in required_scorers:
        try:
            result = available[name](image_path)
        except EvaluationUnavailable:
            raise
        except Exception as exc:
            raise EvaluationUnavailable(f"required scorer {name!r} failed") from exc
        if not isinstance(result, ScorerResult):
            raise EvaluationUnavailable(
                f"required scorer {name!r} did not return structured ScorerResult evidence"
            )
        if not isinstance(result.passed, bool):
            raise EvaluationUnavailable(
                f"required scorer {name!r} returned non-boolean passed evidence"
            )
        if not isinstance(result.version, str) or not result.version.strip():
            raise EvaluationUnavailable(
                f"required scorer {name!r} returned no version provenance"
            )
        if not isinstance(result.labels, list) or not all(
            isinstance(label, str) for label in result.labels
        ):
            raise EvaluationUnavailable(
                f"required scorer {name!r} returned malformed labels evidence"
            )
        versions[name] = result.version
        dimensions[name] = result.score
        labels.extend(result.labels)
        passed = passed and result.passed

    return EvaluationResult(
        passed=passed,
        labels=labels,
        dimensions=dimensions,
        scorer_versions=versions,
    )
