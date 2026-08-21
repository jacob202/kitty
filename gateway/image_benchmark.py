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


@dataclass(frozen=True)
class ImageBenchmarkSuite:
    """Collection of Image Lab benchmark cases."""

    name: str
    cases: list[ImageBenchmarkCase]


def default_image_benchmark_suite() -> ImageBenchmarkSuite:
    """Initial regression suite for conversational image workflows."""
    return ImageBenchmarkSuite(
        name="image_lab_v1",
        cases=[
            ImageBenchmarkCase(
                name="identity_preservation",
                scorers=["identity"],
                metadata={"goal": "Character identity remains stable across a new scene."},
            ),
            ImageBenchmarkCase(
                name="anchor_edit",
                scorers=["anchor_edit"],
                metadata={"goal": "An anchored image edit preserves the source intent."},
            ),
            ImageBenchmarkCase(
                name="protected_traits",
                scorers=["protected_traits"],
                metadata={"goal": "Protected character traits remain unchanged."},
            ),
            ImageBenchmarkCase(
                name="requested_changes",
                scorers=["requested_changes"],
                metadata={"goal": "Requested changes are applied without unrelated drift."},
            ),
        ],
    )


@dataclass
class ImageBenchmarkSuiteResult:
    suite: str
    passed: bool
    results: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite": self.suite,
            "passed": self.passed,
            "results": list(self.results),
        }


def run_benchmark_suite(
    suite: ImageBenchmarkSuite,
    *,
    image_path: str,
    scorers: dict[str, Callable[[str], Any]],
) -> ImageBenchmarkSuiteResult:
    """Run all cases and return deterministic evidence."""
    results: list[dict[str, Any]] = []
    passed = True

    for case in suite.cases:
        result = run_benchmark_case(
            case,
            image_path=image_path,
            scorers=scorers,
        )
        results.append(result.to_dict())
        passed = passed and result.passed

    return ImageBenchmarkSuiteResult(
        suite=suite.name,
        passed=passed,
        results=results,
    )
