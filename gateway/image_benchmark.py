"""Image Lab benchmark runner.

Keeps benchmark execution separate from generation providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from gateway.image_evaluation import EvaluationResult, evaluate_image


@dataclass(frozen=True)
class ImageBenchmarkCase:
    name: str
    scorers: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageBenchmarkResult:
    case: str
    passed: bool
    evaluation: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case": self.case,
            "passed": self.passed,
            "evaluation": self.evaluation,
        }


def run_benchmark_case(
    case: ImageBenchmarkCase,
    *,
    image_path: str,
    scorers: dict[str, Callable[[str], Any]],
) -> ImageBenchmarkResult:
    """Execute one deterministic benchmark case."""
    result: EvaluationResult = evaluate_image(
        image_path=image_path,
        required_scorers=case.scorers,
        scorers=scorers,
    )
    return ImageBenchmarkResult(
        case=case.name,
        passed=result.passed,
        evaluation=result.to_dict(),
    )
