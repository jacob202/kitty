from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.session_learning import (
    SignalError,
    Store,
    compare_capability_runs,
    fingerprint,
    load_signals,
    record_evaluation_signal,
    record_signal,
    summarize_signals,
)

NOW = datetime(2026, 8, 1, 20, 0, tzinfo=timezone.utc)


def payload(**overrides: str) -> dict[str, str]:
    value = {
        "stable_key": "duplicate-chat-foundation-work",
        "category": "duplicate_work",
        "severity": "medium",
        "summary": "A second worker began rebuilding an already-owned chat slice.",
        "evidence": "Open PR and branch touched the same Chat runtime files.",
        "impact": "Wasted worker time and created a merge collision.",
        "suggested_change": "Make next-work resolution reject overlapping active paths.",
        "source_session": "test-session",
        "verified_by": "fixture",
    }
    value.update(overrides)
    return value


def test_fingerprint_is_stable() -> None:
    assert fingerprint("duplicate-chat-foundation-work") == fingerprint(
        "duplicate-chat-foundation-work"
    )
    assert fingerprint("duplicate-chat-foundation-work") != fingerprint(
        "different-signal"
    )


def test_first_noncritical_signal_is_observed(tmp_path: Path) -> None:
    result = record_signal(
        payload(), store=Store(tmp_path, "test"), now=NOW
    )
    signal = result["signal"]

    assert signal["occurrence_count"] == 1
    assert signal["promotion_status"] == "observe"
    assert Path(result["path"]).exists()


def test_second_occurrence_promotes(tmp_path: Path) -> None:
    store = Store(tmp_path, "test")
    first = record_signal(payload(), store=store, now=NOW)
    second = record_signal(
        payload(source_session="second-session"),
        store=store,
        now=NOW.replace(hour=21),
    )

    assert first["signal"]["promotion_status"] == "observe"
    assert second["signal"]["occurrence_count"] == 2
    assert second["signal"]["promotion_status"] == "promote"
    assert "repeated" in second["signal"]["promotion_reason"]


def test_same_source_session_is_idempotent_and_does_not_promote(tmp_path: Path) -> None:
    store = Store(tmp_path, "test")
    first = record_signal(payload(), store=store, now=NOW)
    repeated = record_signal(payload(), store=store, now=NOW.replace(hour=21))

    assert first["created"] is True
    assert repeated["created"] is False
    assert repeated["signal"]["occurrence_count"] == 1
    assert repeated["signal"]["promotion_status"] == "observe"
    assert len(load_signals(tmp_path)) == 1

    with pytest.raises(SignalError, match="already exists with different signal content"):
        record_signal(
            payload(summary="The same session changed its evidence."),
            store=store,
            now=NOW.replace(hour=22),
        )


def test_same_second_distinct_sessions_are_retained_without_collision(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path, "test")
    payloads = [payload(), payload(source_session="second-session")]

    with ThreadPoolExecutor(max_workers=2) as executor:
        recorded = list(
            executor.map(lambda raw: record_signal(raw, store=store, now=NOW), payloads)
        )

    assert all(item["created"] is True for item in recorded)
    assert recorded[0]["path"] != recorded[1]["path"]
    signals = load_signals(tmp_path)
    assert len(signals) == 2
    assert {signal["source_session"] for signal in signals} == {
        "test-session",
        "second-session",
    }
    assert max(signal["occurrence_count"] for signal in signals) == 2


def test_integrity_signal_promotes_immediately(tmp_path: Path) -> None:
    result = record_signal(
        payload(
            stable_key="fabricated-success-receipt",
            category="fabricated_success",
            severity="high",
        ),
        store=Store(tmp_path, "test"),
        now=NOW,
    )

    assert result["signal"]["occurrence_count"] == 1
    assert result["signal"]["promotion_status"] == "promote"


def test_unknown_keys_fail_loud(tmp_path: Path) -> None:
    bad = payload()
    bad["surprise"] = "silent schema drift"

    with pytest.raises(SignalError, match="unknown signal keys"):
        record_signal(bad, store=Store(tmp_path, "test"), now=NOW)


def test_corrupt_existing_store_fails_loud(tmp_path: Path) -> None:
    (tmp_path / "bad.json").write_text("not-json", encoding="utf-8")

    with pytest.raises(SignalError, match="invalid JSON"):
        load_signals(tmp_path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("unexpected", "value", "unknown"),
        ("category", "not-a-category", "category must be one of"),
        ("severity", "not-a-severity", "severity must be one of"),
        ("summary", "", "summary must be a non-empty string"),
        ("fingerprint", "0" * 16, "mismatched fingerprint"),
        ("id", "wfs_wrong", "expected"),
        ("occurrence_count", 0, "at least 1"),
        ("window_days", 0, "at least 1"),
        ("promotion_status", "unknown", "promotion_status"),
        ("promotion_reason", "invented", "promotion_reason"),
    ],
)
def test_retained_signal_schema_corruption_fails_loud(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    result = record_signal(payload(), store=Store(tmp_path, "test"), now=NOW)
    path = Path(result["path"])
    stored = json.loads(path.read_text(encoding="utf-8"))
    stored[field] = value
    path.write_text(json.dumps(stored), encoding="utf-8")

    with pytest.raises(SignalError, match=message):
        load_signals(tmp_path)


def test_retained_signal_count_must_match_distinct_source_sessions(tmp_path: Path) -> None:
    result = record_signal(payload(), store=Store(tmp_path, "test"), now=NOW)
    path = Path(result["path"])
    stored = json.loads(path.read_text(encoding="utf-8"))
    stored["occurrence_count"] = 2
    stored["promotion_status"] = "promote"
    stored["promotion_reason"] = "repeated in 2 sessions within the window"
    path.write_text(json.dumps(stored), encoding="utf-8")

    with pytest.raises(SignalError, match=r"expected \[1\] distinct source_session"):
        load_signals(tmp_path)


def test_summary_groups_and_ranks_promoted_signals(tmp_path: Path) -> None:
    store = Store(tmp_path, "test")
    record_signal(payload(), store=store, now=NOW)
    record_signal(
        payload(source_session="second-session"),
        store=store,
        now=NOW.replace(hour=21),
    )
    record_signal(
        payload(
            stable_key="one-off-tool-flake",
            category="tool_failure",
            severity="low",
            summary="One tool call failed once.",
            suggested_change="Observe before changing the workflow.",
        ),
        store=store,
        now=NOW.replace(hour=22),
    )

    result = summarize_signals(load_signals(tmp_path), now=NOW.replace(hour=23))

    assert result["total_signals"] == 3
    assert result["unique_signals"] == 2
    assert result["promoted"][0]["stable_key"] == "duplicate-chat-foundation-work"
    assert result["promoted"][0]["occurrence_count"] == 2
    assert result["observed"][0]["stable_key"] == "one-off-tool-flake"


def test_written_signal_is_valid_json(tmp_path: Path) -> None:
    result = record_signal(payload(), store=Store(tmp_path, "test"), now=NOW)
    written = json.loads(Path(result["path"]).read_text(encoding="utf-8"))

    assert written == result["signal"]

# --- paired capability evaluation and distilled learning ------------------


def test_compare_capability_runs_measures_only_matched_tasks() -> None:
    result = compare_capability_runs(
        {"task-a": 0.50, "task-b": 0.70},
        {"task-a": 0.80, "task-b": 0.90},
        minimum_lift=0.10,
        context={"model": "same-model", "workspace": "same-worktree", "scorer": "acceptance-v1"},
    )

    assert result["task_keys"] == ["task-a", "task-b"]
    assert result["pair_count"] == 2
    assert result["baseline_mean"] == pytest.approx(0.60)
    assert result["candidate_mean"] == pytest.approx(0.85)
    assert result["absolute_lift"] == pytest.approx(0.25)
    assert result["improved"] is True
    assert result["context"]["model"] == "same-model"


def test_compare_capability_runs_rejects_unmatched_task_sets() -> None:
    with pytest.raises(SignalError, match="identical task keys"):
        compare_capability_runs(
            {"task-a": 0.5},
            {"task-b": 0.8},
            context={"model": "m", "workspace": "w", "scorer": "s"},
        )


def test_compare_capability_runs_respects_minimum_lift() -> None:
    result = compare_capability_runs(
        {"task-a": 0.70, "task-b": 0.70},
        {"task-a": 0.74, "task-b": 0.74},
        minimum_lift=0.05,
        context={"model": "m", "workspace": "w", "scorer": "s"},
    )

    assert result["absolute_lift"] == pytest.approx(0.04)
    assert result["improved"] is False


def test_non_improving_candidate_does_not_create_a_learning_signal(tmp_path: Path) -> None:
    evaluation = compare_capability_runs(
        {"task-a": 0.8},
        {"task-a": 0.7},
        context={"model": "m", "workspace": "w", "scorer": "s"},
    )

    result = record_evaluation_signal(
        evaluation,
        stable_key="candidate-harness-lift",
        capability_name="candidate harness",
        source_session="eval-1",
        store=Store(tmp_path, "test"),
        now=NOW,
    )

    assert result["created"] is False
    assert result["signal"] is None
    assert load_signals(tmp_path) == []


def test_repeated_positive_paired_evidence_promotes_through_existing_learning_store(
    tmp_path: Path,
) -> None:
    evaluation = compare_capability_runs(
        {"task-a": 0.4, "task-b": 0.6},
        {"task-a": 0.7, "task-b": 0.8},
        minimum_lift=0.1,
        context={"model": "m", "workspace": "w", "scorer": "s"},
    )
    store = Store(tmp_path, "test")

    first = record_evaluation_signal(
        evaluation,
        stable_key="candidate-harness-lift",
        capability_name="candidate harness",
        source_session="eval-1",
        store=store,
        now=NOW,
    )
    second = record_evaluation_signal(
        evaluation,
        stable_key="candidate-harness-lift",
        capability_name="candidate harness",
        source_session="eval-2",
        store=store,
        now=NOW.replace(hour=21),
    )

    assert first["signal"]["category"] == "capability_improvement"
    assert first["signal"]["promotion_status"] == "observe"
    assert second["signal"]["occurrence_count"] == 2
    assert second["signal"]["promotion_status"] == "promote"
    assert "baseline_mean=0.500000" in second["signal"]["evidence"]
    assert "candidate_mean=0.750000" in second["signal"]["evidence"]



def test_tampered_positive_evaluation_cannot_create_learning_signal(tmp_path: Path) -> None:
    evaluation = compare_capability_runs(
        {"task-a": 0.8},
        {"task-a": 0.4},
        minimum_lift=0.1,
        context={"model": "m", "workspace": "w", "scorer": "s"},
    )
    tampered = dict(evaluation)
    tampered["improved"] = True
    tampered["absolute_lift"] = 0.5

    with pytest.raises(SignalError, match="evaluation"):
        record_evaluation_signal(
            tampered,
            stable_key="tampered-capability-lift",
            capability_name="tampered capability",
            source_session="eval-tampered",
            store=Store(tmp_path, "test"),
            now=NOW,
        )

    assert load_signals(tmp_path) == []
