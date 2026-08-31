"""Small deterministic metrics for repeated Kitty reliability evidence."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

SCHEMA_VERSION = 1


class ReliabilityMetricError(ValueError):
    """Raised when a reliability receipt cannot be represented truthfully."""


def summarize_repetitions(
    runs: Sequence[Mapping[str, Any]],
    *,
    head_sha: str,
    scenario_ids: Sequence[str],
) -> dict[str, Any]:
    """Summarize repeated executions; reliability requires every run to pass."""
    if not runs:
        raise ReliabilityMetricError("at least one repetition is required")
    if not isinstance(head_sha, str) or not head_sha.strip():
        raise ReliabilityMetricError("head_sha must be a non-empty string")
    if not scenario_ids or not all(
        isinstance(item, str) and item.strip() for item in scenario_ids
    ):
        raise ReliabilityMetricError("scenario_ids must contain non-empty strings")

    normalized: list[dict[str, Any]] = []
    for index, run in enumerate(runs, start=1):
        exit_code = run.get("exit_code")
        duration_ms = run.get("duration_ms")
        if isinstance(exit_code, bool) or not isinstance(exit_code, int):
            raise ReliabilityMetricError(f"run {index} exit_code must be an integer")
        if (
            isinstance(duration_ms, bool)
            or not isinstance(duration_ms, (int, float))
            or not math.isfinite(float(duration_ms))
            or float(duration_ms) < 0
        ):
            raise ReliabilityMetricError(
                f"run {index} duration_ms must be a finite non-negative number"
            )
        normalized.append(
            {
                **dict(run),
                "repetition": index,
                "exit_code": exit_code,
                "duration_ms": round(float(duration_ms), 3),
                "passed": exit_code == 0,
            }
        )

    passed = sum(bool(run["passed"]) for run in normalized)
    repetitions = len(normalized)
    return {
        "schema_version": SCHEMA_VERSION,
        "head_sha": head_sha.strip(),
        "scenario_ids": list(scenario_ids),
        "repetitions": repetitions,
        "passed_repetitions": passed,
        "success_rate": passed / repetitions,
        "all_passed": passed == repetitions,
        "max_duration_ms": max(float(run["duration_ms"]) for run in normalized),
        "runs": normalized,
    }
