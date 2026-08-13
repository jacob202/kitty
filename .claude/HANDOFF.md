# Handoff — CI is back; KPROOF-001 is paused on a blocker main already fixed

<!-- kitty-handoff
{
  "schema_version": 2,
  "updated_at": "2026-08-11T08:05:00Z",
  "branch": "claude/next-4gj621",
  "worktree": "main",
  "status": "complete",
  "execution_owner": "interactive",
  "completed_items": [
    "Established that the GitHub Actions outage ended on 2026-08-10 between 23:03:51Z and 23:20:19Z: Tests runs went from 3-13 second no-runner failures to 200-314 second real executions",
    "Found main at d54fd896 red on lint and typecheck, both in mcp/builder/context.py; recorded it and corrected docs/PROJECT_STATUS.md, which still declared CI dead and main at ece1bad (PR #454, merged)",
    "Fixed the seven mcp/imagen type errors CI cannot see; superseded by #460 mid-flight, so PR #467 was closed with an empty diff",
    "Read the live Builder projection from Jacob's Mac: 109 tasks, KPROOF-001 paused on a data-directory blocker that main now fixes"
  ],
  "blockers": [
    "This GitHub-connected container cannot inspect Jacob's Mac checkout, services, credentials, providers, or local Builder database; the Builder projection fails here on a missing pydantic import",
    "Jacob's canonical checkout cannot check out main: the amphipod worktree holds it"
  ],
  "next_action": "none",
  "parallel_work": [
    {
      "kind": "pull_request",
      "ref": "#468 docs(audit): AAA-1 decision audit, PAA-1 store classification, ADR collision fix (claude/reoi-issues-yvpsx6)",
      "owner": "other session; not this one",
      "observed_at": "2026-08-11T08:00:00Z",
      "touches": ["docs/", "no overlap with this branch"]
    },
    {
      "kind": "pull_request",
      "ref": "#465 feat(builder): add Codex CLI fallback adapter (feat/codex-builder-adapter)",
      "owner": "other session; not this one",
      "observed_at": "2026-08-11T08:00:00Z",
      "touches": ["gateway/", "no overlap with this branch"]
    },
    {
      "kind": "branch",
      "ref": "origin/feat/agent-council-relay, 5 commits beyond main and not an ancestor of it; PR #458 already merged at an earlier head",
      "owner": "other session; not this one",
      "observed_at": "2026-08-11T08:00:00Z",
      "touches": ["mcp/imagen/", "gateway/", "scripts/", "tests/", "carries a third independent imagen fix that main has since superseded"]
    }
  ],
  "recommendations": [
    {
      "id": "resume-kproof-001",
      "what": "Resume KPROOF-001 through Builder's supported operator path",
      "why": "It paused itself at 2026-08-10 23:04 because its task worktree base d54fd896 lacked the KITTY_BUILDER_DATA_DIR fix and workers were reading checkout-local Builder state. That fix is on main in b4ab8b0. The mission deadline is 2026-08-18.",
      "class": "code",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    },
    {
      "id": "ci-typecheck-imagen-requirements",
      "what": "Install requirements.txt and mcp/imagen/requirements.txt in the Tests workflow typecheck job",
      "why": "The typecheck job installs only mypy and four stub packages and no project dependencies at all, so every third-party import across gateway/, mcp/, and workers/ resolves to Any. Seven real mcp/imagen errors sat on main unseen and surfaced only through the local pre-push hook, where they blocked every push. CI-scope, so it needs Jacob's approval.",
      "class": "code",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    }
  ],
  "invalidation_conditions": [
    "KPROOF-001 leaves the paused state, which retires the resume recommendation",
    "main moves beyond dda9868 in a way that touches mcp/imagen/ or .github/workflows/tests.yml",
    "GitHub Actions stops executing again, which would restore the need for out-of-band verification",
    "docs/ACTIVE_MISSION.md no longer names KPROOF-001 as the running mission"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null,
  "head_sha": "7c18b8e83571e63450ff24d1d6a6eec1f74a8088",
  "kb_receipt": "kbr_e24216337393bb50acbb"
}
-->

## What this handoff replaces

The previous checkpoint tracked PR #458 as `OPEN` and carried
`review-merge-pr-458` as ready. That PR **merged** at 2026-08-11T00:57:05Z at
head `7ec0bd9`, which fired its own invalidation condition. The recommendation is
dropped as complete, not deferred.

## Outcome

Two pull requests, one merged and one closed:

- **[#454](https://github.com/jacob202/kitty/pull/454) — merged** at `bcc4e7d`.
  Docs only. It recorded the end of the Actions outage, recorded what `main` was
  red on, and corrected `docs/PROJECT_STATUS.md`, which still declared CI dead
  and `main` at `ece1bad`.
- **[#467](https://github.com/jacob202/kitty/pull/467) — closed, unmerged.** It
  fixed the seven `mcp/imagen` type errors, passed 11 green checks, and was
  superseded while in CI by `cd35d96` (via #460). The conflict was resolved in
  `main`'s favour, which left the branch with an empty diff.

No code is left on `claude/next-4gj621`: its `mcp/imagen` changes were resolved
in `main`'s favour. What remains is this closeout — the checkpoint, the KB
payload, the effectiveness receipt, and two workflow signals — published as
PR #471 because this container is ephemeral and unpushed evidence is lost.

## The headline: the Actions outage is over

It ended on 2026-08-10 between 23:03:51Z and 23:20:19Z. Duration is the tell —
no-runner failures end in 3–13 seconds, real `Tests` runs take 200–314 seconds.
Last dead run `a736ee52` at 23:03:51Z; first live run `59900f20` at 23:20:19Z.

Out-of-band verification is retired. CI is authoritative again, and red checks
carry information again. Any document describing red checks as meaningless is
describing the pre-23:20Z window only.

## The live Builder baseline, read from Jacob's Mac

109 tasks: 51 done, 43 cancelled, 10 blocked, 3 queued, 1 running, 1 failed,
across 33 initiatives.

`KPROOF-001` is **paused**, with this recorded reason:

> Proof blocker: task worktree base d54fd896 lacks the local
> KITTY_BUILDER_DATA_DIR path fix, so worker status commands created/read
> checkout-local Builder state. Pause before retrying on split state.

That is the machine refusing to continue on split state — the behaviour the
mission exists to prove. **The blocker is already fixed**: `b4ab8b0 fix(builder):
honor canonical data directory` is on `main`, and both `gateway/paths.py` and
`mcp/builder/context.py` honour `KITTY_BUILDER_DATA_DIR`. `KPROOF-RETRY-001` was
pre-built at 23:57 and is also paused.

This session did not claim, execute, or schedule any Builder work. Resuming is an
operator action and belongs to Jacob.

## Verification

Reproducing every `Tests` job with the workflow's own commands, at bare
`d54fd896`: ruff **FAIL** (1), mypy **FAIL** (1), pytest **3987 passed** / 2
deselected / 29 subtests / **78.40%** vs a 73% floor, vitest **341 passed** / 45
files, `next build` clean, playwright **29 passed / 15 skipped**, vulture exit 0.
With the repair: ruff clean, mypy clean over 293 files, pytest **3987 passed /
78.38%**. PR #454 then passed **12 green checks** on real runners.

Imagen work: mypy **7 errors in 3 files → Success, no issues found in 279 source
files** with `google-genai` and `google-api-core` installed, and clean again in a
venv holding only `requirements.txt`. ruff clean. `pytest -k "imagen or retry"` —
**108 passed**. PR #467: **11 green checks**.

Two selected failures are container artifacts, not defects. Both live in
`tests/test_builder_loop.py`: `TestRecoveryExercise::test_killed_run_packet_recovers_end_to_end`
is load-sensitive and passes uncontended, and
`TestRunPacket::test_operator_pause_between_attempts_stops_retry` shells out to a
hardcoded `python3.12` that has no project dependencies here — it fails
identically with all changes stashed.

## Boundaries and unavailable sources

- Builder's read-only projection **failed in this container** (`ModuleNotFoundError:
  pydantic`). Unavailable, not empty. The Builder facts above come from Jacob's
  Mac, pasted into the session.
- `~/kb` **does not exist here**. Nothing was consulted; wiki entries,
  corrections, the effectiveness receipt, and both workflow signals are staged in
  the repo fallback.
- `gh` is not installed; open PRs were read through the GitHub MCP instead of the
  survey's `gh` path.
- `origin/feat/agent-council-relay` and PRs #465, #468 belong to other sessions.
  Leave them alone.

## Session records

- Execution owner: `interactive`.
- KB entries consulted / used / stale: **0 / 0 / 0** — `~/kb` unavailable.
- Effectiveness receipt: `kbr_e24216337393bb50acbb` in
  `docs/session-notes/kb-effectiveness.jsonl`. Outcome `completed_unreviewed`;
  token, cost, elapsed-time, and independent-review measurements are all
  unavailable.
- Staged KB payload: `docs/session-notes/2026-08-11-kb-payload.md`.
- Workflow signals, both first occurrences at `observe`, in
  `docs/session-notes/workflow-signals/`:
  - `parallel-lanes-duplicate-same-fix` (duplicate_work, high) — three lanes
    independently produced the same repairs to the same files in one night; two
    of this session's three code changes were discarded after full verification.
  - `ci-cannot-typecheck-imagen-deps` (missing_automation, medium).
- **Repeat detection is currently broken across stores.** The previous session
  recorded `local-prepush-ci-divergence` for the same underlying divergence into
  `~/kb` on the Mac; this session's related signal went to the repo fallback
  under a different stable key. Neither will see the other until the payload is
  synced and the keys are reconciled.

## Next action

**None for this session.** Its assignment is complete: both pull requests are
resolved and the branch has no diff against `origin/main`.

The next move lives in `recommendations`, which is the cross-session channel.
The top-ranked ready item is **resume `KPROOF-001`** — its recorded blocker
landed on `main` in `b4ab8b0` and no longer applies. That is an operator action
on Builder's queue and belongs to Jacob, not to a bare continuation.
