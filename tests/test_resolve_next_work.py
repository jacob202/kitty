"""Tests for the interactive/Builder execution-owner boundary resolver.

These codify the acceptance criteria for the "interactive vs builder" boundary
(ADR 0025 section 10-11; ADR 0026 "One execution owner"):

- a valid interactive checkpoint continues without using Builder as a task source;
- no interactive resolution produces a Builder side effect or touches the queue;
- explicit ``builder next`` / a valid Builder bundle enter the Builder lane
  without changing bare ``next`` semantics;
- reviewing Builder output does not transfer implementation ownership;
- every resolution records exactly one execution owner.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import resolve_next_work as rnw

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "resolve_next_work.py"

ALL_OWNERS = {"interactive", "builder"}


def _clijson(*args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    ("kwargs", "expected_owner", "expected_resolution"),
    [
        # Valid interactive checkpoint -> continue interactive, no Builder source.
        (
            {"valid_interactive_checkpoint": True},
            "interactive",
            rnw.Resolution.CONTINUE_INTERACTIVE,
        ),
        # No checkpoint and no Builder entrypoint -> explicit no-op.
        (
            {},
            "interactive",
            rnw.Resolution.EXPLICIT_NOOP,
        ),
        # Explicit builder next -> governed Builder selection.
        (
            {"explicit_builder_intent": True},
            "builder",
            rnw.Resolution.BUILDER_SELECT,
        ),
        # Valid Builder bundle -> governed Builder selection.
        (
            {"valid_builder_bundle": True},
            "builder",
            rnw.Resolution.BUILDER_SELECT,
        ),
        # Pure review of Builder output stays interactive, no ownership transfer.
        (
            {"review_only": True},
            "interactive",
            rnw.Resolution.REVIEW_BUILDER,
        ),
    ],
)
def test_matrix(kwargs, expected_owner, expected_resolution):
    work = rnw.resolve_next_work(**kwargs)
    assert work.execution_owner == expected_owner
    assert work.resolution == expected_resolution


def test_every_resolution_records_exactly_one_execution_owner():
    """Each outcome names exactly one owner, and only the two allowed values."""
    outcomes = [
        rnw.resolve_next_work(),
        rnw.resolve_next_work(valid_interactive_checkpoint=True),
        rnw.resolve_next_work(explicit_builder_intent=True),
        rnw.resolve_next_work(valid_builder_bundle=True),
        rnw.resolve_next_work(review_only=True),
    ]
    for work in outcomes:
        assert work.execution_owner in ALL_OWNERS


def test_valid_interactive_checkpoint_never_uses_builder_as_task_source():
    """A bare interactive continuation carries no Builder side effects."""
    work = rnw.resolve_next_work(valid_interactive_checkpoint=True)
    assert work.is_builder_lane is False
    assert work.builder_side_effects == ()
    assert work.leaves_queued_tasks_unchanged is True
    assert not work.to_dict()["builder_side_effects"]


def test_noop_leaves_queued_builder_tasks_unchanged():
    """The explicit no-op neither consumes nor changes Builder queue state."""
    work = rnw.resolve_next_work()
    assert work.resolution is rnw.Resolution.EXPLICIT_NOOP
    assert work.execution_owner == "interactive"
    assert work.builder_side_effects == ()
    assert work.leaves_queued_tasks_unchanged is True


def test_interactive_resolutions_never_hold_a_builder_side_effect():
    """None of the interactive resolutions can apply/select/run/claim/drain."""
    interactive_resolutions = [
        rnw.Resolution.CONTINUE_INTERACTIVE,
        rnw.Resolution.EXPLICIT_NOOP,
        rnw.Resolution.REVIEW_BUILDER,
    ]
    for resolution in interactive_resolutions:
        work = rnw.resolve_next_work(
            valid_interactive_checkpoint=(resolution is rnw.Resolution.CONTINUE_INTERACTIVE),
            review_only=(resolution is rnw.Resolution.REVIEW_BUILDER),
        )
        assert work.is_builder_lane is False
        assert work.builder_side_effects == ()


def test_builder_entrypoints_enter_governed_lane_without_changing_bare_next():
    """Explicit builder next / valid bundle use the Builder lane and the
    controlled side effects; the bare interactive `next` semantics are unchanged
    and remain a separate decision."""
    for kwargs in (
        {"explicit_builder_intent": True},
        {"valid_builder_bundle": True},
    ):
        work = rnw.resolve_next_work(**kwargs)
        assert work.is_builder_lane is True
        assert work.execution_owner == "builder"
        assert work.resolution is rnw.Resolution.BUILDER_SELECT
        assert set(work.builder_side_effects) == set(rnw.BUILDER_SIDE_EFFECTS)
        assert work.leaves_queued_tasks_unchanged is False

    # Bare interactive next is still interactive-only regardless of Builder lane.
    bare = rnw.resolve_next_work(valid_interactive_checkpoint=True)
    assert bare.is_builder_lane is False
    assert bare.execution_owner == "interactive"


def test_review_does_not_transfer_implementation_ownership():
    """Reviewing Builder output keeps the interactive execution owner."""
    work = rnw.resolve_next_work(review_only=True)
    assert work.execution_owner == "interactive"
    assert work.resolution is rnw.Resolution.REVIEW_BUILDER
    assert work.builder_side_effects == ()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"valid_builder_bundle": True, "review_only": True},
        {"explicit_builder_intent": True, "review_only": True},
    ],
)
def test_contradictory_intent_fails_loudly(kwargs):
    """A review-only Builder entrypoint is ambiguous and must not silently
    choose a lane; it raises instead (fail loud, never mask)."""
    with pytest.raises(ValueError):
        rnw.resolve_next_work(**kwargs)


def test_cli_reports_decision_as_read_only_json():
    payload = _clijson("--valid-interactive-checkpoint")
    assert payload["execution_owner"] == "interactive"
    assert payload["resolution"] == rnw.Resolution.CONTINUE_INTERACTIVE.value
    assert payload["is_builder_lane"] is False
    assert payload["builder_side_effects"] == []


def test_cli_noop_leaf_unchanged():
    payload = _clijson()
    assert payload["resolution"] == rnw.Resolution.EXPLICIT_NOOP.value
    assert payload["execution_owner"] == "interactive"
    assert payload["leaves_queued_tasks_unchanged"] is True


def test_cli_builder_bundle_enters_builder_lane():
    payload = _clijson("--valid-builder-bundle")
    assert payload["execution_owner"] == "builder"
    assert payload["resolution"] == rnw.Resolution.BUILDER_SELECT.value
    assert payload["is_builder_lane"] is True
