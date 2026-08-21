"""Fail-closed Image Lab evaluation contract.

Keeps evaluation separate from generation. A missing required scorer is an
infrastructure failure, never a passing result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


class EvaluationUnavailable(RuntimeError):
    """Raised when a required evaluator is not available."""


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
    available = scorers or {}
    missing = [name for name in required_scorers if name not in available]
    if missing:
        raise EvaluationUnavailable(
            f"required scorers unavailable: {', '.join(sorted(missing))}"
        )

    dimensions: dict[str, Any] = {}
    versions: dict[str, str] = {}
    for name in required_scorers:
        result = available[name](image_path)
        versions[name] = getattr(result, "version", "unknown")
        dimensions[name] = getattr(result, "score", result)

    return EvaluationResult(
        passed=True,
        dimensions=dimensions,
        scorer_versions=versions,
    )
