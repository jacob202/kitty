# KH-CONT-04 — a merged pull request must not block publication

**Initiative:** kitty-hardening-v1
**Owner:** builder
**Depends on:** none
**Free or paid:** free

## What Jacob can do after this

Keep pushing after a PR merges, instead of every lane in the repository being
blocked until someone hand-edits a continuity file.

## Why this is the next thing

On 2026-09-16 nothing could be pushed. Both checkpoints declared PR #877 `OPEN`
at `fc911dd4`. It had merged as `59b878cb`. `_checkpoint_pull_request_check` in
`gateway/context_receipt_legacy.py` compares the recorded state against GitHub,
finds the contradiction, and returns FAIL — which fails four tests in
`tests/test_check_continuity_state.py`, which fails the pre-push gate, for
everyone, on every branch.

The failure is correct in the narrow sense and useless in every other. Nothing
was wrong with the tree being pushed. The only way through was to edit
`.claude/STATE.md` and `.claude/HANDOFF.md`, which `CLAUDE.md` says not to touch
during ordinary work and which several lanes had deliberately left alone to avoid
clobbering each other. So the lane before this one pushed with `--no-verify`
instead, and the gate taught people to bypass it.

A merged PR is not a contradiction. It is the ordinary end of a pull request, and
the checkpoint simply has not caught up. A PR that is still open at a head the
checkpoint does not recognise is a real contradiction — that is live work
disagreeing with the record — and must keep failing.

## Plan

1. In `_checkpoint_pull_request_check`, separate the merged case from the
   open-at-a-different-head case.
2. Merged becomes a WARN naming the PR and its merge commit, so the record's
   staleness is visible without blocking anyone.
3. Open at a different head than recorded stays a FAIL. So does closed without
   merging: the recorded work did not land, and that is worth stopping for.
4. Make the WARN say what to do — that the checkpoint should be reconciled, and
   that its pull request field takes `null` when the session has no active PR.
   That is the documented value for "no active PR claimed" and the thing nobody
   knew when this was first repaired by hand.
5. Leave the absent-PR path exactly as it is; it already passes.

## Not in scope

Rewriting, generating, or reconciling checkpoints automatically. A checkpoint is
another session's record and writing it from here is how the collisions this
repository already has a signal for get worse. Changing what the receipt checks
about heads, branches, or ancestry. Relaxing any other FAIL.

## Verification

**Tier 1 — mechanical.**

```
python -m pytest -q -m "integration or not integration" tests/test_check_continuity_state.py
python -m ruff check gateway/context_receipt_legacy.py
```

Today this collects 9 tests. It passed only after a checkpoint was hand-edited on
2026-09-16; before that edit, four of the nine failed against a checkpoint naming
a merged PR. The new cases must cover merged, open-at-a-different-head, closed
unmerged, and absent, so the distinction is pinned rather than assumed.

**Tier 2 — running app.** Not applicable.

**Tier 3 — product acceptance.** Not applicable.

## Stop condition

Stop and escalate if merged and closed-unmerged cannot be told apart from the
data the receipt already has. Treating them alike in either direction is wrong:
one is the ordinary end of a PR and one means the work never landed. If that
requires a second GitHub call, say so rather than guessing from the state string.

## Recovery

Confined to one function and its tests. Revert to `HEAD` and re-run. Note that
reverting restores the blocking behaviour, so if a checkpoint anywhere still
names a merged PR the repository goes back to being unpushable — reconcile that
checkpoint before reverting, not after.
