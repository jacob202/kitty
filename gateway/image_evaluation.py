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
class EvaluationMetric:
    """A named benchmark dimension with optional versioned scoring."""

    name: str
    score: Any
    passed: bool = True
    evidence: dict[str, Any] = field(default_factory=dict)
    version: str = "unknown"


@dataclass
class EvaluationResult:
    passed: bool
    labels: list[str] = field(default_factory=list)
    dimensions: dict[str, Any] = field(default_factory=dict)
    scorer_versions: dict[str, str] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "labels": list(self.labels),
            "dimensions": dict(self.dimensions),
            "scorer_versions": dict(self.scorer_versions),
            "evidence": dict(self.evidence),
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
    evidence: dict[str, Any] = {}
    passed = True
    for name in required_scorers:
        result = available[name](image_path)
        if isinstance(result, EvaluationMetric):
            dimensions[name] = result.score
            versions[name] = result.version
            evidence[name] = result.evidence
            passed = passed and result.passed
        else:
            dimensions[name] = result
            versions[name] = getattr(result, "version", "unknown")

    return EvaluationResult(
        passed=passed,
        dimensions=dimensions,
        scorer_versions=versions,
        evidence=evidence,
    )
