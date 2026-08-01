import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import kb_effectiveness as kb

NOW = datetime(2026, 8, 1, 21, 0, tzinfo=timezone.utc)


def payload(session_id: str = "s1", **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "schema_version": 1,
        "session_id": session_id,
        "recorded_at": "2026-08-01T20:00:00Z",
        "execution_owner": "interactive",
        "tool": "claude-code",
        "task_class": "code_change",
        "outcome": "accepted",
        "kb_entries_consulted": ["wiki/a.md", "corrections/b.md"],
        "kb_entries_used": ["wiki/a.md"],
        "kb_entries_stale_or_wrong": ["corrections/b.md"],
        "promoted_to_canonical": ["tests/test_example.py"],
        "kb_tokens_loaded": 120,
        "total_tokens": 1000,
        "estimated_cost_usd": 0.2,
        "elapsed_seconds": 60,
        "attempts": 1,
        "repair_commits": 0,
        "regressions": 0,
        "first_pass_approved": True,
        "duplicate_work_avoided": True,
        "correction_prevented": False,
        "result_id": "pr-1",
        "task_id": None,
        "initiative_id": None,
        "packet_id": None,
        "branch": "feat/test",
        "head_sha": "a" * 40,
        "notes": "verified",
    }
    base.update(overrides)
    return base


def test_record_is_idempotent(tmp_path: Path) -> None:
    store = kb.Store(tmp_path / "receipts.jsonl", "test")
    first = kb.record_receipt(payload(), store=store, now=NOW)
    second = kb.record_receipt(payload(), store=store, now=NOW)
    assert first["created"] is True
    assert second["created"] is False
    assert first["receipt_id"] == second["receipt_id"]
    assert len(store.path.read_text().splitlines()) == 1


def test_conflicting_session_id_fails(tmp_path: Path) -> None:
    store = kb.Store(tmp_path / "receipts.jsonl", "test")
    kb.record_receipt(payload(), store=store, now=NOW)
    with pytest.raises(kb.ReceiptError, match="session_id already exists"):
        kb.record_receipt(payload(total_tokens=999), store=store, now=NOW)


def test_unknown_key_fails() -> None:
    with pytest.raises(kb.ReceiptError, match="unknown receipt keys"):
        kb.validate_payload(payload(extra="no"), now=NOW)


def test_used_and_stale_must_be_consulted() -> None:
    with pytest.raises(kb.ReceiptError, match="subset"):
        kb.validate_payload(payload(kb_entries_used=["missing.md"]), now=NOW)
    with pytest.raises(kb.ReceiptError, match="both useful and stale"):
        kb.validate_payload(
            payload(kb_entries_stale_or_wrong=["wiki/a.md"]), now=NOW
        )


def test_corrupt_store_fails_loud(tmp_path: Path) -> None:
    path = tmp_path / "receipts.jsonl"
    path.write_text('{"bad":\n', encoding="utf-8")
    with pytest.raises(kb.ReceiptError, match="invalid JSON"):
        kb.load_receipts(path)


def test_summary_computes_rates(tmp_path: Path) -> None:
    store = kb.Store(tmp_path / "receipts.jsonl", "test")
    kb.record_receipt(payload("s1"), store=store, now=NOW)
    kb.record_receipt(
        payload(
            "s2",
            execution_owner="builder",
            tool="builder-worker",
            kb_entries_consulted=[],
            kb_entries_used=[],
            kb_entries_stale_or_wrong=[],
            promoted_to_canonical=[],
            total_tokens=2000,
            kb_tokens_loaded=None,
            attempts=2,
            first_pass_approved=False,
            duplicate_work_avoided=False,
            result_id="pr-2",
        ),
        store=store,
        now=NOW,
    )
    result = kb.summarize_receipts(kb.load_receipts(store.path), now=NOW)
    assert result["sessions"] == 2
    assert result["accepted_results"] == 2
    assert result["kb_retrieval"]["usefulness_rate"] == 0.5
    assert result["kb_retrieval"]["stale_or_wrong_rate"] == 0.5
    assert result["quality"]["first_pass_approval_rate"] == 0.5
    assert result["efficiency"]["average_attempts"] == 1.5
    assert result["execution_owners"] == {"interactive": 1, "builder": 1}


def test_unknown_measurements_are_not_zero(tmp_path: Path) -> None:
    store = kb.Store(tmp_path / "receipts.jsonl", "test")
    unknown = payload(
        total_tokens=None,
        kb_tokens_loaded=None,
        estimated_cost_usd=None,
        attempts=None,
        repair_commits=None,
        regressions=None,
        first_pass_approved=None,
        duplicate_work_avoided=None,
        correction_prevented=None,
    )
    kb.record_receipt(unknown, store=store, now=NOW)
    result = kb.summarize_receipts(kb.load_receipts(store.path), now=NOW)
    assert result["efficiency"]["total_tokens_known_sessions"] == 0
    assert result["efficiency"]["total_tokens"] is None
    assert result["efficiency"]["kb_tokens_loaded"] is None
    assert result["efficiency"]["estimated_cost_usd"] is None
    assert result["efficiency"]["repair_commits"] is None
    assert result["efficiency"]["average_attempts"] is None
    assert result["quality"]["first_pass_approval_rate"] is None
    assert result["quality"]["regressions"] is None
    assert result["quality"]["duplicate_work_avoided"] is None
    assert result["quality"]["corrections_prevented"] is None
    assert "total token counts are incomplete" in result["insufficient_evidence"]


def test_receipt_requires_stable_timestamp_and_accepted_result_identity() -> None:
    missing_timestamp = payload()
    missing_timestamp.pop("recorded_at")
    with pytest.raises(kb.ReceiptError, match="recorded_at"):
        kb.validate_payload(missing_timestamp, now=NOW)

    with pytest.raises(kb.ReceiptError, match="accepted receipts require result_id"):
        kb.validate_payload(payload(result_id=None), now=NOW)


def test_duplicate_accepted_result_fails_before_it_can_be_double_counted(
    tmp_path: Path,
) -> None:
    store = kb.Store(tmp_path / "receipts.jsonl", "test")
    kb.record_receipt(payload("interactive-session"), store=store, now=NOW)

    with pytest.raises(kb.ReceiptError, match="accepted result_id already exists"):
        kb.record_receipt(
            payload(
                "builder-session",
                execution_owner="builder",
                tool="builder-worker",
            ),
            store=store,
            now=NOW,
        )


def test_mutated_history_fails_chain_validation(tmp_path: Path) -> None:
    store = kb.Store(tmp_path / "receipts.jsonl", "test")
    kb.record_receipt(payload("s1"), store=store, now=NOW)
    kb.record_receipt(payload("s2", result_id="pr-2"), store=store, now=NOW)

    lines = store.path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["store_scope"] = "mutated"
    lines[0] = json.dumps(first)
    store.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(kb.ReceiptError, match="chain"):
        kb.load_receipts(store.path)


def test_report_marks_comparison_non_causal(tmp_path: Path) -> None:
    store = kb.Store(tmp_path / "receipts.jsonl", "test")
    kb.record_receipt(payload(), store=store, now=NOW)
    summary = kb.summarize_receipts(kb.load_receipts(store.path), now=NOW)
    report = kb.render_report(summary)
    assert "does not prove causation" in report
    assert "Evidence gaps" in report
    assert "Sample too small: True" in report


def test_summary_accepts_window_days_after_subcommand() -> None:
    args = kb.build_parser().parse_args(["summary", "--window-days", "14"])

    assert args.window_days == 14
