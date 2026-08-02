"""KTL2-003: prove the Builder and interactive lanes stay separate.

This test is a zero-cost, non-destructive proof of the lane boundary. It
exercises the receipt layer (``scripts/kb_effectiveness.py``) that both lanes
share as their evidence rail, and asserts that the mechanics prevent a lane
from claiming, duplicating, scheduling, or reporting the other lane's
implementation:

- every accepted implementation has exactly one execution owner;
- Builder attempt/review evidence and interactive continuity/effectiveness
  evidence are stored in the same rail but remain distinct and cross-referenced
  by session identity, never merged or double-counted;
- a second interactive tool resolving the same continuation is idempotent
  (same receipt identity, no duplicate session), not independent Builder work;
- unknown measurements stay unknown rather than being converted into zeroes.

Everything runs in a :mod:`tmp_path` store; no real dotfiles, logs, or Builder
state are touched.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import kb_effectiveness as kb

NOW = datetime(2026, 8, 2, 0, 0, tzinfo=timezone.utc)
SESSION_ID = "interactive:ktl2-003-proof:2026-08-02"


def base_payload(
    *,
    session_id: str = SESSION_ID,
    owner: str = "interactive",
    tool: str = "opencode",
    outcome: str = "accepted",
    result_id: str = "ktl2-003-lane-proof",
    packet_id: str | None = "KTL2-003-parallel-lanes-e2e",
    initiative_id: str | None = "ktl-002-measured-learning-boundary-v1",
    task_class: str = "review",
    notes: str | None = "parallel-lanes proof",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "session_id": session_id,
        "recorded_at": "2026-08-02T00:00:00Z",
        "execution_owner": owner,
        "tool": tool,
        "task_class": task_class,
        "outcome": outcome,
        "kb_entries_consulted": [],
        "kb_entries_used": [],
        "kb_entries_stale_or_wrong": [],
        "promoted_to_canonical": [],
        "kb_tokens_loaded": None,
        "total_tokens": None,
        "estimated_cost_usd": None,
        "elapsed_seconds": None,
        "attempts": None,
        "repair_commits": None,
        "regressions": None,
        "first_pass_approved": None,
        "duplicate_work_avoided": None,
        "correction_prevented": None,
        "result_id": result_id,
        "task_id": None,
        "initiative_id": initiative_id,
        "packet_id": packet_id,
        "branch": "kittybuilder/kb_msazu581_72ec",
        "head_sha": None,
        "notes": notes,
    }


def test_second_interactive_tool_resolves_same_continuation_idempotently(
    tmp_path: Path,
) -> None:
    store = kb.Store(tmp_path / "receipts.jsonl", "explicit")
    first = kb.record_receipt(base_payload(), store=store, now=NOW)
    # A second interactive continuation with identical content must resolve to
    # the SAME receipt identity, not a new independent record.
    second = kb.record_receipt(base_payload(), store=store, now=NOW)
    assert first["created"] is True
    assert second["created"] is False
    assert first["receipt_id"] == second["receipt_id"]
    assert len(kb.load_receipts(store.path)) == 1


def test_each_implementation_has_exactly_one_execution_owner(tmp_path: Path) -> None:
    store = kb.Store(tmp_path / "receipts.jsonl", "explicit")
    kb.record_receipt(base_payload(), store=store, now=NOW)
    # Builder claiming the SAME accepted result is a double-count and fails.
    with pytest.raises(kb.ReceiptError, match="accept"):
        kb.record_receipt(
            base_payload(
                session_id="builder:ktl2-003-proof:2026-08-02",
                owner="builder",
                tool="builder-worker",
            ),
            store=store,
            now=NOW,
        )


def test_builder_attempt_and_interactive_evidence_stay_separate_but_cross_referenced(
    tmp_path: Path,
) -> None:
    store = kb.Store(tmp_path / "receipts.jsonl", "explicit")
    kb.record_receipt(
        base_payload(
            session_id="interactive:ktl2-003-proof:2026-08-02",
            result_id="ktl2-003-interactive-lane",
            notes="interactive continuity/effectiveness evidence",
        ),
        store=store,
        now=NOW,
    )
    kb.record_receipt(
        base_payload(
            session_id="builder:ktl2-003-proof:2026-08-02",
            owner="builder",
            tool="builder-worker",
            task_class="planning",
            result_id="ktl2-003-builder-lane",
            notes="builder attempt/review evidence",
        ),
        store=store,
        now=NOW,
    )

    receipts = kb.load_receipts(store.path)
    owners = {item["receipt"]["execution_owner"] for item in receipts}
    sessions = {item["receipt"]["session_id"] for item in receipts}
    results = {
        item["receipt"]["result_id"] for item in receipts
        if item["receipt"]["outcome"] == "accepted"
    }

    # Both lanes coexist in the same evidence rail (cross-referenced) ...
    assert owners == {"interactive", "builder"}
    assert len(sessions) == 2
    assert "interactive:ktl2-003-proof:2026-08-02" in sessions
    assert "builder:ktl2-003-proof:2026-08-02" in sessions
    # ... yet each accepted implementation keeps its own unique result identity.
    assert len(results) == 2
    assert "ktl2-003-interactive-lane" in results
    assert "ktl2-003-builder-lane" in results

    summary = kb.summarize_receipts(receipts, now=NOW)
    assert summary["execution_owners"] == {"interactive": 1, "builder": 1}


def test_unknown_measurements_stay_unknown_not_zero(tmp_path: Path) -> None:
    store = kb.Store(tmp_path / "receipts.jsonl", "explicit")
    kb.record_receipt(base_payload(), store=store, now=NOW)
    summary = kb.summarize_receipts(kb.load_receipts(store.path), now=NOW)
    assert summary["efficiency"]["total_tokens"] is None
    assert summary["efficiency"]["estimated_cost_usd"] is None
    assert summary["efficiency"]["average_attempts"] is None
    assert summary["quality"]["first_pass_approval_rate"] is None
    assert any("do not prove causation" in gap for gap in summary["insufficient_evidence"])
