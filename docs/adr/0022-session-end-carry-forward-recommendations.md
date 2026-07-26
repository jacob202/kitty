# ADR 0022: Session-End Recommendations Carry Forward In The Checkpoint

- **Status:** Proposed
- **Date:** 2026-07-26
- **Decision owner:** Jacob
- **Relates to:** ADR 0016 (life-first ordering), ADR 0020 (one canonical roadmap)

## Context

Session end already produced `.claude/STATE.md`, `.claude/HANDOFF.md`, and a
`~/kb/NOW.md` update, but it produced them blind: it recorded what this session
did without inspecting the other worktrees, unmerged branches, open PRs, and
Builder tasks in flight at the same time. Recommendations written that way
either ignore collisions or hand-wave at them.

The obvious fix — let session end write free-text notes for a future session-end
run to "take into consideration" — creates a fifth memory surface alongside
STATE, HANDOFF, NOW, and `config/SOUL_SCRATCHPAD.md`. Prose notes addressed to a
future run have no reader, no expiry, and no way to tell whether the thing they
were waiting on ever happened. "Let the other work finish first" written as
prose is indistinguishable from an excuse, and it silently repeats forever.

## Decision

Deferred next steps carry forward as **structured, condition-keyed entries in
the existing checkpoint**, not as a new notes file.

1. `.claude/STATE.md` gains two optional fields at `schema_version: 2` —
   `parallel_work` (what else was in flight, observed, not remembered) and
   `recommendations` (at most three ranked next steps, life projects before code
   per ADR 0016).
2. Each recommendation carries a stable `id`. Re-deferring reuses the id and
   increments `deferred_count`, so a stuck item is visible as stuck rather than
   reappearing as a fresh idea.
3. A `deferred` recommendation must name a `release_check`: a shell command that
   exits 0 exactly when the blocker is gone. `gateway/context_receipt.py`
   rejects a deferred entry without one, so an unfalsifiable "wait for the other
   work" fails the continuity gate instead of shipping.
4. Session end begins by running `scripts/session_end_survey.sh` (read-only) and
   by executing each carried `release_check`. Consumption is mechanical; nothing
   depends on a future model remembering to re-read prose.
5. Deferral requires a real collision or dependency. Unrelated parallel work is
   not a blocker.

`schema_version: 1` checkpoints stay readable — they simply carry nothing.

## Consequences

- The carry-forward channel is the checkpoint. Session end must not open a
  parallel notes file for its own future runs.
- `./kitty context --agent` surfaces carried recommendations at cold start, so
  the next session inherits them without reading the skill.
- A recommendation that cannot be given a `release_check` is not blocked; it is
  undecided, and must be reported to Jacob as a decision rather than parked.
- `deferred_count` reaching 3 is a signal that the stated blocker is not the
  real one, and session end says so out loud.
- Survey sources that cannot be reached (no `gh`, no `~/kb`, no Builder DB)
  report `UNAVAILABLE` and are never rendered as clean results.

## Revisit trigger

Revisit if recommendations routinely outlive the checkpoint they were written
in — that would mean they are backlog items and belong in the roadmap under
ADR 0020, not in session state.
