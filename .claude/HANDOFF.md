# Handoff — UI failure-copy and status truthfulness power run

<!-- kitty-handoff
{
  "schema_version": 2,
  "updated_at": "2026-08-29T23:30:00Z",
  "head_sha": "9c60762a2626dd2cc02da7cf1513780e0581fb26",
  "branch": "claude/kitty-power-run-l4dvwx",
  "worktree": ".",
  "status": "complete",
  "completed_items": [
    "Booted the real product (production build + hermetic gateway) and exercised all eight surfaces at 1440x900 and iPhone 14/14 Pro under available, degraded, and fully-stopped backend states",
    "Added describeFailure() as the single render-boundary translator for thrown gateway/query errors; routed Home, Projects, Documents and Library through it with working retry controls",
    "Reworded RuntimeBadge so it describes the backend connection only, ending the contradictory 'ready' + 'Kitty status unknown' pairing",
    "Persisted the Safari install-prompt dismissal to localStorage so it survives reload",
    "Gave the chat composer, chat search and Image Lab prompt accessible names that survive typing",
    "Ran the independent product acceptance review requested on head c648eb52 and returned FAIL on one clause of three",
    "Fixed that FAIL in c15defa; it was later superseded by the #672 merge, which solved the same defect more broadly",
    "Reconciled the #672 merge in 9c60762: took their model-availability rework, restored two fixes their merge reverted by accident, and fixed the brief row leak it newly exposed"
  ],
  "blockers": [
    "Current head has had no independent acceptance pass: the same session that ran the acceptance review also wrote the fix and the merge resolution"
  ],
  "next_action": "none",
  "invalidation_conditions": [
    "PR #675 merges or closes",
    "origin/main advances past e2b7a06 and the branch is no longer mergeable clean",
    "Someone pushes to claude/kitty-power-run-l4dvwx past 9c60762"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": {
    "number": 675,
    "state": "OPEN",
    "head_sha": "9c60762a2626dd2cc02da7cf1513780e0581fb26"
  },
  "parallel_work": [
    {
      "kind": "pull_request",
      "ref": "https://github.com/jacob202/kitty/pull/673",
      "owner": "jacob202",
      "touches": [
        "gateway/",
        "scripts/",
        "tests/"
      ],
      "observed_at": "2026-08-29T23:28:00Z"
    }
  ],
  "recommendations": [
    {
      "id": "independent-acceptance-9c60762",
      "what": "Run an independent product acceptance pass on PR #675 head 9c60762, then lift draft so CI actually executes",
      "why": "This session ran the acceptance review, wrote the fix, and resolved the #672 merge, so it is not independent for the current head; and every CI job is gated on draft == false, so nothing is machine-validated yet",
      "class": "code",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    },
    {
      "id": "model-picker-503-leak",
      "what": "Remove the raw HTTP status from #672's model-picker copy ('model picker returned 503'), which its own StatusBar test asserts",
      "why": "It is a raw HTTP status in product copy \u2014 the same defect class PR #675 exists to remove \u2014 but it is recently-merged deliberate work, so changing it inside a merge resolution would reverse someone else's decision without review",
      "class": "code",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    },
    {
      "id": "dead-eslint-config",
      "what": "Delete gateway/kitty-chat/eslint.config.mjs, or restore the eslint dev dependencies it imports",
      "why": "It imports @eslint/eslintrc and eslint-config-next, neither in package.json, and nothing in the Makefile or CI invokes eslint, so JS/TS linting cannot have run for some time; make lint is Python ruff only",
      "class": "code",
      "status": "deferred",
      "blocked_by": "deleting the file was refused by this environment's permission guard; needs Jacob or a session permitted to remove it",
      "release_check": "test -f gateway/kitty-chat/eslint.config.mjs",
      "deferred_count": 2,
      "first_deferred": "2026-08-29"
    }
  ]
}
-->

**Identity:** interactive Claude Code session, 2026-08-29.
**Branch:** `claude/kitty-power-run-l4dvwx` @ `9c60762`, clean, pushed.
**PR:** [#675](https://github.com/jacob202/kitty/pull/675) — open, **draft**, `mergeable_state: clean`.

**Invalid once** #675 merges or closes, `origin/main` advances past `e2b7a06`
such that the branch stops being mergeable clean, or anyone pushes past
`9c60762`.

## What this session did

Jacob asked for a polish/hardening power run: find the highest-leverage problem
in the real product, fix it, verify it, keep going.

The finding, from driving the actual app against a backend that answers
`/health` but 404s most endpoints: **Kitty told you several different, partly
false stories about whether it was working.** Home showed raw
`Gateway returned 404 Not Found` in three panels, the bare word `unavailable` in
three more, and only one of six offered a retry. The top strip simultaneously
read `ready`, `Kitty status unknown`, and `gateway offline`.

Fixed across six commits (three of them landed by another lane while this
session was rate-limited — see STATE.md for the commit table):

- `describeFailure()` in `src/lib/failure-copy.ts` is now the single place a
  thrown fetch/query error becomes user-facing copy. `gateway.ts` still returns
  the raw diagnostic form; translation happens at the render boundary.
- All six Home panels, plus Projects, Documents, and Library, go through it and
  have working retries.
- `RuntimeBadge` describes the backend connection only, so it can no longer be
  read as a second claim about Kitty's overall state.
- The Safari install banner stays dismissed across reloads.
- The chat composer, chat search, and Image Lab prompt have accessible names
  that survive typing.
- **`c15defa`**: `StatusBar` no longer claims the gateway is offline while it is
  running.

## Changed paths

```
gateway/kitty-chat/src/lib/failure-copy.ts            (new)
gateway/kitty-chat/src/app/page.tsx
gateway/kitty-chat/src/components/HomeState.tsx
gateway/kitty-chat/src/components/TopBar.tsx
gateway/kitty-chat/src/components/StatusBar.tsx
gateway/kitty-chat/src/components/CrayonCat.tsx
gateway/kitty-chat/src/components/ProjectsPanel.tsx
gateway/kitty-chat/src/components/DocumentsPanel.tsx
gateway/kitty-chat/src/components/LibraryView.tsx
gateway/kitty-chat/src/components/InputBar.tsx
gateway/kitty-chat/src/components/SessionSidebar.tsx
gateway/kitty-chat/src/components/ImageLab.tsx
gateway/kitty-chat/src/components/KittyRuntimeProvider.tsx
+ matching tests under gateway/kitty-chat/tests/
```

## Execution owner

**interactive.** No Builder packet was claimed, consumed, or scheduled. Builder's
queue DB is not present in this container, so its state is **unknown, not
empty**.

## Other owners' in-flight work — do not touch

- PR #673 `closeout/finish-open-loops-20260829` (Jacob) — `gateway/`, `scripts/`, `tests/`
- PR #672 merged into `main` as `e2b7a06`; its status-row rework is now reconciled into this branch at `9c60762`.
- PR #674 merged into `main` during this session as `3fc28ed`.

## Blocker

**Head `9c60762` has had no independent acceptance pass.** This session ran the
acceptance review Jacob requested (against `c648eb52`), returned FAIL, wrote the
fix, and then resolved the #672 merge. That makes it non-independent for the
current head, so the PR stays draft rather than self-certifying.

Because every CI job is gated on `draft == false`, all checks report `skipped`.
Nothing is red, but nothing is CI-validated either. Lifting draft both satisfies
the gate mechanically and gets real CI coverage.

## Next move

Get an independent product acceptance pass on `9c60762` under
`docs/PRODUCT_ACCEPTANCE.md`, then lift draft on #675.

The user goal to review against, unchanged from Jacob's request:

> A person should be able to understand whether Kitty is working when part of it
> fails, recover without seeing developer-facing HTTP/route/internal
> diagnostics, and use Kitty's primary text-entry fields with assistive
> technology without those fields becoming anonymous after typing starts.

Reproduce the harness: `npm run build`, then `next start` on port 4110 against a
gateway that answers `/health` and 404s the rest; sweep all eight surfaces at
1440×900 and iPhone 14 Pro; also test the gateway fully stopped.

## Deferred

- **`dead-eslint-config`** — `gateway/kitty-chat/eslint.config.mjs` imports
  `@eslint/eslintrc` and `eslint-config-next`, neither in `package.json`, and
  nothing in the Makefile or CI invokes eslint, so JS/TS linting cannot have run
  for some time. (`make lint` is Python ruff only, which is why it passes.)
  Recommend deleting the dead config; the type check and 546 tests already carry
  that load. **Not done here**: the delete was blocked by a permission guard in
  this environment, and working around that would have been wrong. One command
  clears it: `git rm gateway/kitty-chat/eslint.config.mjs`.
  Release check: `test -f gateway/kitty-chat/eslint.config.mjs`

## Known-unfixed, deliberately out of scope

`src/components/ProviderCenter.tsx:82` still uses `gateway offline` as a
status-dot label. Left alone: it sits inside the provider diagnostics panel in
Settings where it contradicts nothing, and chasing it would have widened this PR.

## KB

`~/kb` is **absent** in this container (`/root/kb` does not exist). It was
deliberately **not** created — per `CLAUDE.md`, creating it silently redirects
every receipt and signal into unversioned container storage that dies with the
container. Entries consulted: 0. Used: 0. Stale/wrong: 0. The effectiveness
receipt is staged at `docs/session-notes/kb-effectiveness.jsonl`.

Token, cost, and elapsed-time fields are `null` — no measurement source was
available to this session. Do not backfill them from intuition.

## Exact verification results

At `9c60762` unless noted:

- `npx vitest run` — **567 passed, 75 files, 0 failed** (baseline at session start: 508)
- `npx tsc --noEmit -p tsconfig.json` — clean
- `npm run build` — succeeded
- `npx playwright test` — **30 passed, 20 skipped, 0 failed** (at `1d25d05`; the 20 skips are project-scoping, desktop-only vs phone-only)
- `pytest` on the four provider tests covering the merged `config/providers.json` — **43 passed**
- Runtime sweep, 8 surfaces × desktop + iPhone 14 Pro, degraded backend — no jargon, no horizontal overflow, no unnamed controls, 16/16 combinations clean
- Gateway fully stopped, both viewports — single plain offline screen, navigation still reachable, no jargon
- ESLint — **could not run**, see deferred item above
