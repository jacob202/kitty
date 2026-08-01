"""Deterministically resolve what a ``next`` / continuation means.

Bare ``next`` in Claude Code, OpenCode, or Codex continues only the current
interactive assignment. It must never apply an initiative, claim a packet,
select or run queued work, or drain KittyBuilder. Explicit ``builder next`` and a
valid Builder-launched bundle are separate, governed Builder entrypoints, and a
pure review of Builder output never transfers implementation ownership.

This module is the tested encoding of that boundary (ADR 0025 section 10-11;
ADR 0026 "One execution owner"). It is a pure decision function: it classifies
intent and records exactly one execution owner. It does not inspect or mutate
Builder state.

    Execution owner: interactive | builder      (exactly one per implementation)
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from enum import Enum


class ExecutionOwner(str, Enum):
    """The single lane that owns an implementation."""

    INTERACTIVE = "interactive"
    BUILDER = "builder"


class Resolution(str, Enum):
    """The concrete outcome of resolving a continuation instruction."""

    CONTINUE_INTERACTIVE = "continue_interactive"
    BUILDER_SELECT = "builder_select"
    REVIEW_BUILDER = "review_builder"
    EXPLICIT_NOOP = "explicit_noop"


# Builder mutations that a bare interactive ``next`` must never perform. Only the
# explicit Builder lane is ever allowed to reach for these, and only through the
# governed selection/execution workflow of ``builder next`` / a valid bundle.
BUILDER_SIDE_EFFECTS: tuple[str, ...] = (
    "apply_initiative",
    "select_packet",
    "run_packet",
    "claim_task",
    "drain_queue",
)


@dataclass(frozen=True)
class NextWork:
    """The resolved meaning of one continuation invocation.

    ``execution_owner`` is always exactly ``"interactive"`` or ``"builder"``.
    ``builder_side_effects`` is empty for the interactive lane and populated
    only for the governed Builder lane, so no interactive resolution can consume
    Builder work.
    """

    execution_owner: str
    resolution: Resolution
    builder_side_effects: tuple[str, ...]

    @property
    def is_builder_lane(self) -> bool:
        return self.execution_owner == ExecutionOwner.BUILDER.value

    @property
    def leaves_queued_tasks_unchanged(self) -> bool:
        """True when this resolution does not select, run, or drain queued work."""
        return not self.is_builder_lane

    def to_dict(self) -> dict:
        return {
            "execution_owner": self.execution_owner,
            "resolution": self.resolution.value,
            "is_builder_lane": self.is_builder_lane,
            "leaves_queued_tasks_unchanged": self.leaves_queued_tasks_unchanged,
            "builder_side_effects": list(self.builder_side_effects),
        }


def resolve_next_work(
    *,
    explicit_builder_intent: bool = False,
    valid_builder_bundle: bool = False,
    valid_interactive_checkpoint: bool = False,
    review_only: bool = False,
) -> NextWork:
    """Resolve a continuation invocation into a lane and outcome.

    Parameters
    ----------
    explicit_builder_intent:
        The user explicitly invoked Builder work (``builder next``, ``take the
        next Builder packet``, or named a Builder task/initiative/packet).
    valid_builder_bundle:
        This process was launched by Builder with a valid packet/task bundle and
        a live lease proving it is Builder-owned.
    valid_interactive_checkpoint:
        There is a valid, non-terminal checkpoint owned by this interactive
        session on this branch/HEAD/PR.
    review_only:
        This invocation is a pure review of Builder output, not implementation.

    Raises
    ------
    ValueError
        On contradictory input (``review_only`` combined with a Builder
        entrypoint), so intent disagreements fail loudly instead of silently
        choosing a lane.
    """
    if valid_builder_bundle and review_only:
        raise ValueError(
            "A valid Builder-launched bundle and a review-only intent are "
            "contradictory: a Builder-owned worker cannot simultaneously be an "
            "independent interactive review that keeps its own ownership."
        )
    if explicit_builder_intent and review_only:
        raise ValueError(
            "Explicit Builder intent and review-only intent are contradictory: "
            "selecting Builder work is not a review, and a review does not "
            "transfer implementation ownership."
        )

    if valid_builder_bundle:
        return NextWork(
            execution_owner=ExecutionOwner.BUILDER.value,
            resolution=Resolution.BUILDER_SELECT,
            builder_side_effects=BUILDER_SIDE_EFFECTS,
        )

    if explicit_builder_intent:
        return NextWork(
            execution_owner=ExecutionOwner.BUILDER.value,
            resolution=Resolution.BUILDER_SELECT,
            builder_side_effects=BUILDER_SIDE_EFFECTS,
        )

    if review_only:
        # Reviewing Builder output stays in the interactive lane and never
        # transfers implementation ownership (ADR 0026).
        return NextWork(
            execution_owner=ExecutionOwner.INTERACTIVE.value,
            resolution=Resolution.REVIEW_BUILDER,
            builder_side_effects=(),
        )

    if valid_interactive_checkpoint:
        return NextWork(
            execution_owner=ExecutionOwner.INTERACTIVE.value,
            resolution=Resolution.CONTINUE_INTERACTIVE,
            builder_side_effects=(),
        )

    # No valid interactive assignment: an explicit no-op. It must not fabricate
    # work or reach into the Builder queue.
    return NextWork(
        execution_owner=ExecutionOwner.INTERACTIVE.value,
        resolution=Resolution.EXPLICIT_NOOP,
        builder_side_effects=(),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve what a continuation instruction means and print the "
            "decision as JSON. Read-only: never inspects or mutates Builder."
        )
    )
    parser.add_argument(
        "--explicit-builder-intent",
        action="store_true",
        help="User explicitly invoked Builder work (builder next / named packet).",
    )
    parser.add_argument(
        "--valid-builder-bundle",
        action="store_true",
        help="Process was launched by Builder with a valid packet bundle.",
    )
    parser.add_argument(
        "--valid-interactive-checkpoint",
        action="store_true",
        help="A valid interactive checkpoint exists for this session.",
    )
    parser.add_argument(
        "--review-only",
        action="store_true",
        help="This invocation reviews Builder output only.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    work = resolve_next_work(
        explicit_builder_intent=args.explicit_builder_intent,
        valid_builder_bundle=args.valid_builder_bundle,
        valid_interactive_checkpoint=args.valid_interactive_checkpoint,
        review_only=args.review_only,
    )
    print(json.dumps(work.to_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
