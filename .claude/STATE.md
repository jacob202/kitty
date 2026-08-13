# Session State — CI is back; KPROOF-001 is paused on a blocker that is now fixed

<!-- kitty-state
{
  "schema_version": 2,
  "updated_at": "2026-08-11T08:05:00Z",
  "branch": "claude/next-4gj621",
  "worktree": "main",
  "status": "complete",
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
  "head_sha": "7c18b8e83571e63450ff24d1d6a6eec1f74a8088"
}
-->

## Execution ownership

- this session: `interactive`
- Builder parallel state: read from Jacob's Mac projection at 2026-08-11 00:0xZ
  and reproduced here only as evidence. This session claimed, executed, and
  scheduled nothing in Builder's queue.

## KB effectiveness

- receipt: `kbr_e24216337393bb50acbb` in `~/kb/metrics/kb-effectiveness.jsonl`, mirrored at `docs/session-notes/kb-effectiveness.jsonl`
- consulted: 0
- used: 0
- stale/wrong: 0
- token/quality evidence gaps: `~/kb` did not exist at session start, so nothing was
  consulted and retrieval usefulness is unmeasurable for this session. It was
  created and populated before close. Token,
  cost, and elapsed-time measurement is unavailable from this harness. The
  outcome is `completed_unreviewed`, not `accepted`: PR #454 merged on 12 green
  checks, but CI is a gate and no independent human review happened.

## What this session established

**The Actions outage is over.** It ended on 2026-08-10 between 23:03:51Z and
23:20:19Z. `Tests` runs went from 3–13 second no-runner failures to 200–314
second real executions. Out-of-band verification is retired; CI is authoritative
again, and red checks are information again. Full method and timings:
[`docs/audit/MAIN_GATE_VERIFICATION_2026-08-10.md`](../docs/audit/MAIN_GATE_VERIFICATION_2026-08-10.md).

**`main` was red before it lifted.** `d54fd896` failed `lint` and `typecheck`,
both in `mcp/builder/context.py`, landed as a direct-to-`main` squash with no
green check. Fixed in #453. Recorded in #454 along with the `PROJECT_STATUS`
correction.

**The live Builder baseline exists now.** From Jacob's Mac: 109 tasks — 51 done,
43 cancelled, 10 blocked, 3 queued, 1 running, 1 failed, across 33 initiatives.
`KPROOF-001` is **paused**, and its recorded reason is precise: the task worktree
base `d54fd896` lacked the `KITTY_BUILDER_DATA_DIR` fix, so worker status
commands created and read checkout-local Builder state. It paused rather than
retry on split state. `KPROOF-RETRY-001` was pre-built at 23:57 and is also
paused.

**That blocker is fixed.** `b4ab8b0 fix(builder): honor canonical data directory`
is on `main`; `gateway/paths.py` and `mcp/builder/context.py` both honour
`KITTY_BUILDER_DATA_DIR`.

## Exact verification results

At bare `d54fd896`, reproducing every `Tests` job with the workflow's own
commands: ruff **FAIL** (1 error), mypy **FAIL** (1 error), pytest **3987
passed** / 2 deselected / 29 subtests / **78.40%** vs a 73% floor, vitest **341
passed** / 45 files, `next build` clean, playwright **29 passed / 15 skipped**,
vulture exit 0.

With the repair applied: ruff clean, mypy clean over 293 files, pytest **3987
passed / 78.38%**. PR #454 then passed **12 green checks** on real runners.

For the imagen work: mypy went from **7 errors in 3 files** to **Success, no
issues found in 279 source files** with `google-genai` and `google-api-core`
installed, and stayed clean in a venv holding only `requirements.txt`. ruff clean.
`pytest -k "imagen or retry"` — **108 passed**, 3894 deselected. PR #467 passed
**11 green checks** before being closed as superseded.

Two selected test failures are container artifacts, not defects:
`tests/test_builder_loop.py::TestRecoveryExercise::test_killed_run_packet_recovers_end_to_end`
(load-sensitive; passes uncontended) and
`::TestRunPacket::test_operator_pause_between_attempts_stops_retry` (shells out
to a hardcoded `python3.12` that has no project dependencies here). The second
fails identically with all changes stashed.

## Dropped recommendation

`review-merge-pr-458` is complete, not deferred. PR #458 merged at
2026-08-11T00:57:05Z by jacob202 at head `7ec0bd9`.

## Unknown until checked on Jacob's Mac

- Gateway, LiteLLM, Open WebUI, `kitty-chat`, and launchd state;
- current provider credentials and quotas;
- whether the one `running` Builder task is live or an orphaned lease from the
  run that paused KPROOF-001;
- whether the merged #437 Builder action behavior works end to end in the
  running application.
