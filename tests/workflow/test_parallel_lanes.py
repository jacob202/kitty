"""KTL2-003 corrective: exercise the real continuation resolver.

The original proof (PR #371) only tested ``scripts.kb_effectiveness.record_receipt``,
not the ``scripts.resolve_next_work`` resolver that KTL2-001 introduced. This
corrective exercises the real resolver and proves:

- bare ``next`` never selects, claims, or touches Builder work;
- explicit ``builder next`` / a valid Builder bundle is the only governed
  Builder entrypoint;
- the resolver is deterministic and never mutates external state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import kb_effectiveness as kb
from scripts import resolve_next_work as rnw

# -- Receipt-layer assertions (secondary evidence only) -------------------------

SUMMARY_NOW = datetime(2026, 8, 2, 2, 0, tzinfo=timezone.utc)


def _receipt_store(tmp_path: Path) -> kb.Store:
    return kb.Store(tmp_path / "receipts.jsonl", "explicit")


def _base_payload(**overrides: object) -> dict[str, object]:
    return {
        "schema_version": 1,
        "session_id": "interactive:corrective:2026-08-02",
        "recorded_at": "2026-08-02T01:00:00Z",
        "execution_owner": "interactive",
        "tool": "opencode",
        "task_class": "review",
        "outcome": "accepted",
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
        "result_id": "ktl2-003-corrective-lane-proof",
        "task_id": None,
        "initiative_id": "ktl-002-measured-learning-boundary-v1",
        "packet_id": "KTL2-003-parallel-lanes-e2e",
        "branch": "main",
        "head_sha": None,
        "notes": "corrective follow-up",
        **overrides,
    }


# --------------------------------------------------------------------------- #
# Resolver tests — the real continuation boundary (primary)
# --------------------------------------------------------------------------- #

class TestBareNextNeverTouchesBuilder:
    """Bare ``next`` (no explicit builder intent, no valid builder bundle) must
    stay interactive-only regardless of what exists in the Builder queue."""

    def test_blank_invocation_is_explicit_noop(self) -> None:
        work = rnw.resolve_next_work()
        assert work.execution_owner == "interactive"
        assert work.resolution is rnw.Resolution.EXPLICIT_NOOP
        assert work.builder_side_effects == ()
        assert work.leaves_queued_tasks_unchanged is True

    def test_valid_interactive_checkpoint_is_continue_interactive(self) -> None:
        work = rnw.resolve_next_work(valid_interactive_checkpoint=True)
        assert work.execution_owner == "interactive"
        assert work.resolution is rnw.Resolution.CONTINUE_INTERACTIVE
        assert work.builder_side_effects == ()
        assert work.leaves_queued_tasks_unchanged is True

    def test_review_only_stays_interactive_and_never_transfers_ownership(
        self,
    ) -> None:
        work = rnw.resolve_next_work(review_only=True)
        assert work.execution_owner == "interactive"
        assert work.resolution is rnw.Resolution.REVIEW_BUILDER
        assert work.builder_side_effects == ()
        assert work.leaves_queued_tasks_unchanged is True


class TestBareNextIgnoresBuilderQueue:
    """The resolver is a pure function — it never inspects Builder state.
    Regardless of what exists in the queue (done, cancelled, blocked,
    queued — any priority), bare ``next`` returns interactive-only."""

    def test_no_existing_packets(self) -> None:
        work = rnw.resolve_next_work()
        assert work.is_builder_lane is False
        assert work.builder_side_effects == ()

    def test_bare_next_with_checkpoint_when_queue_has_eligible_packets(
        self,
    ) -> None:
        work = rnw.resolve_next_work(valid_interactive_checkpoint=True)
        assert work.execution_owner == "interactive"
        assert work.resolution is rnw.Resolution.CONTINUE_INTERACTIVE
        assert work.is_builder_lane is False


class TestBuilderEntrypoints:
    """Explicit ``builder next`` and a valid Builder bundle are the only
    governed paths into the Builder lane."""

    def test_explicit_builder_intent_enters_builder_lane(self) -> None:
        work = rnw.resolve_next_work(explicit_builder_intent=True)
        assert work.execution_owner == "builder"
        assert work.resolution is rnw.Resolution.BUILDER_SELECT
        assert work.is_builder_lane is True
        assert set(work.builder_side_effects) == set(rnw.BUILDER_SIDE_EFFECTS)
        assert work.leaves_queued_tasks_unchanged is False

    def test_valid_builder_bundle_enters_builder_lane(self) -> None:
        work = rnw.resolve_next_work(valid_builder_bundle=True)
        assert work.execution_owner == "builder"
        assert work.resolution is rnw.Resolution.BUILDER_SELECT
        assert work.is_builder_lane is True
        assert set(work.builder_side_effects) == set(rnw.BUILDER_SIDE_EFFECTS)
        assert work.leaves_queued_tasks_unchanged is False

    def test_bare_next_is_unchanged_when_builder_lane_also_exists(self) -> None:
        bare = rnw.resolve_next_work(valid_interactive_checkpoint=True)
        assert bare.execution_owner == "interactive"
        assert bare.is_builder_lane is False

        builder = rnw.resolve_next_work(explicit_builder_intent=True)
        assert builder.execution_owner == "builder"
        assert builder.is_builder_lane is True

    def test_no_interactive_resolution_contains_builder_side_effects(self) -> None:
        for kwargs in (
            {},
            {"valid_interactive_checkpoint": True},
            {"review_only": True},
        ):
            work = rnw.resolve_next_work(**kwargs)
            assert work.is_builder_lane is False
            assert work.builder_side_effects == ()


class TestDeterministicOutput:
    """The resolver is deterministic and never mutates external state."""

    def test_same_input_gives_same_output(self) -> None:
        a = rnw.resolve_next_work(valid_interactive_checkpoint=True)
        b = rnw.resolve_next_work(valid_interactive_checkpoint=True)
        assert a.execution_owner == b.execution_owner
        assert a.resolution == b.resolution
        assert a.builder_side_effects == b.builder_side_effects

    def test_to_dict_is_roundtrip_safe(self) -> None:
        work = rnw.resolve_next_work(explicit_builder_intent=True)
        d = work.to_dict()
        assert d["execution_owner"] == "builder"
        assert d["is_builder_lane"] is True
        assert d["leaves_queued_tasks_unchanged"] is False
        assert set(d["builder_side_effects"]) == set(rnw.BUILDER_SIDE_EFFECTS)


class TestContradictoryIntent:
    """The fail-loud rule applies: contradictory intent raises."""

    def test_bundle_and_review_contradiction(self) -> None:
        with pytest.raises(ValueError):
            rnw.resolve_next_work(valid_builder_bundle=True, review_only=True)

    def test_explicit_builder_and_review_contradiction(self) -> None:
        with pytest.raises(ValueError):
            rnw.resolve_next_work(
                explicit_builder_intent=True, review_only=True
            )


# --------------------------------------------------------------------------- #
# Receipt-layer regression invariants (secondary)
# --------------------------------------------------------------------------- #

def test_second_interactive_tool_resolves_same_continuation_idempotently(
    tmp_path: Path,
) -> None:
    store = _receipt_store(tmp_path)
    first = kb.record_receipt(_base_payload(), store=store)
    second = kb.record_receipt(_base_payload(), store=store)
    assert first["created"] is True
    assert second["created"] is False
    assert first["receipt_id"] == second["receipt_id"]
    assert len(kb.load_receipts(store.path)) == 1


def test_each_implementation_has_exactly_one_execution_owner(
    tmp_path: Path,
) -> None:
    store = _receipt_store(tmp_path)
    kb.record_receipt(_base_payload(), store=store)
    with pytest.raises(kb.ReceiptError, match="accept"):
        kb.record_receipt(
            _base_payload(
                session_id="builder:corrective:2026-08-02",
                execution_owner="builder",
                tool="builder-worker",
            ),
            store=store,
        )


def test_builder_and_interactive_evidence_stay_separate_but_cross_referenced(
    tmp_path: Path,
) -> None:
    store = _receipt_store(tmp_path)
    kb.record_receipt(
        _base_payload(
            session_id="interactive:corrective:2026-08-02",
            result_id="corrective-interactive",
            notes="interactive evidence",
        ),
        store=store,
    )
    kb.record_receipt(
        _base_payload(
            session_id="builder:corrective:2026-08-02",
            execution_owner="builder",
            tool="builder-worker",
            task_class="planning",
            result_id="corrective-builder",
            notes="builder evidence",
        ),
        store=store,
    )
    receipts = kb.load_receipts(store.path)
    owners = {item["receipt"]["execution_owner"] for item in receipts}
    sessions = {item["receipt"]["session_id"] for item in receipts}
    results = {
        item["receipt"]["result_id"]
        for item in receipts
        if item["receipt"]["outcome"] == "accepted"
    }
    assert owners == {"interactive", "builder"}
    assert len(sessions) == 2
    assert len(results) == 2
    summary = kb.summarize_receipts(receipts, now=SUMMARY_NOW)
    assert summary["execution_owners"] == {"interactive": 1, "builder": 1}


def test_unknown_measurements_stay_unknown_not_zero(tmp_path: Path) -> None:
    store = _receipt_store(tmp_path)
    kb.record_receipt(_base_payload(), store=store)
    summary = kb.summarize_receipts(
        kb.load_receipts(store.path), now=SUMMARY_NOW
    )
    assert summary["efficiency"]["total_tokens"] is None
    assert summary["efficiency"]["estimated_cost_usd"] is None
    assert any(
        "do not prove causation" in gap
        for gap in summary["insufficient_evidence"]
    )
