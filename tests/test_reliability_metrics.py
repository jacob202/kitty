from __future__ import annotations

import pytest

from gateway.reliability_metrics import ReliabilityMetricError, summarize_repetitions


def test_all_pass_summary_requires_every_repetition() -> None:
    summary = summarize_repetitions(
        [
            {"exit_code": 0, "duration_ms": 10},
            {"exit_code": 0, "duration_ms": 12},
            {"exit_code": 0, "duration_ms": 9},
        ],
        head_sha="a" * 40,
        scenario_ids=("one", "two"),
    )

    assert summary["repetitions"] == 3
    assert summary["passed_repetitions"] == 3
    assert summary["success_rate"] == 1.0
    assert summary["all_passed"] is True
    assert summary["max_duration_ms"] == 12


def test_one_failure_makes_repeatability_gate_fail() -> None:
    summary = summarize_repetitions(
        [
            {"exit_code": 0, "duration_ms": 10},
            {"exit_code": 1, "duration_ms": 11},
        ],
        head_sha="b" * 40,
        scenario_ids=("failure-injection",),
    )

    assert summary["passed_repetitions"] == 1
    assert summary["success_rate"] == 0.5
    assert summary["all_passed"] is False


def test_summary_rejects_missing_or_malformed_run_evidence() -> None:
    with pytest.raises(ReliabilityMetricError, match="at least one"):
        summarize_repetitions([], head_sha="a" * 40, scenario_ids=("x",))
    with pytest.raises(ReliabilityMetricError, match="exit_code"):
        summarize_repetitions(
            [{"exit_code": True, "duration_ms": 1}],
            head_sha="a" * 40,
            scenario_ids=("x",),
        )
    with pytest.raises(ReliabilityMetricError, match="duration_ms"):
        summarize_repetitions(
            [{"exit_code": 0, "duration_ms": -1}],
            head_sha="a" * 40,
            scenario_ids=("x",),
        )
