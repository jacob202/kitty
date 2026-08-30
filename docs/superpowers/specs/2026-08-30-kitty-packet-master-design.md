# Kitty Packet Master — Product-First Pilot

**Date:** 2026-08-30  
**Status:** approved lean design; written-spec review pending
**Owner:** ChatGPT Packet Master  
**Lane:** product packets and bounded flow-break investigation only

## Decision

Prioritize one user-visible product outcome before building packet infrastructure.
Defer a generated registry, disposition/metadata sidecars, checkpoint tree, and
the 48-wave KFP catalog. The Aug 1–30 evidence audit verified no direct incident
where a duplicate packet ID itself caused harm. Duplicate IDs remain a risk, not
a reason to build a second control plane now.

The first pilot is **LIBRARY-CHAT-001**: a person opens a ready local image in
Library and sends it into Chat with truthful attachment state and no dead
controls. It uses the existing Gateway, ArtifactStore, and native Kitty UI.
Older-history research is not required for this pilot.

## Authority order

1. `docs/ACTIVE_MISSION.md` owns the current objective and acceptance contract.
2. `docs/ROADMAP.md` owns priority and order; it is the sole active roadmap.
3. Accepted ADRs, Constitution, and architecture docs govern design decisions.
4. A packet receipt owns only its bounded implementation contract.
5. Git/GitHub, running-product probes, CI, and supported Builder projections
   outrank prose for current facts.
6. Builder owns durable execution state; it is not inferred from packet files,
   UI emptiness, or old reports.

The current mission sequence remains REC-001 → WORK-001 → BUILDER-001 →
IMAGE-001 → LIBRARY-001 → AUTO-001 → HOME-001 → ACCEPT-001. This document
does not activate a mission or apply a Builder manifest.

## Time-bound evidence snapshot

Captured 2026-08-30; refresh before implementation:

- Fresh GitHub main at capture: `c7a7de0c2b670e968e4443d4ae494159243ccfb3`.
- The Packet Master branch was created earlier from `a1c0f09a...`; it is not
  current-main and must be refreshed/reconciled before publication.
- PR #675 is merged; no current open PR title/branch was found for the
  Library/artifact/attach pilot. This title search does not prove file-level
  non-overlap. Preserved worktrees/open PRs are not active agents without a
  verified owner/lease.
- `kb_mtgatvyi_340e` was observed blocked for `scope_violation` with no owner
  and zero running queue tasks; this is time-bound, and external-process
  absence remains UNKNOWN.
- The canonical checkout is dirty; this lane never edits it.

## Verified pain appendix

### B8 wrong assignment

- Date: 2026-08-02–05.
- Evidence: [B8 forensics](/Users/jacobbrizinnski/Projects/kitty/artifacts/forensic-b8-wrong-assignment-2026-08-05.md:12-24).
- Task: `kb_msb4yx3n_f6e8`; intended onboarding repair was never materialized
  as a Builder task.
- Result: stale attempt 111 reactivated B8; attempts 106–114 ran the unrelated
  trivia-doc packet; commits `7ea5e077`, `9bbc945a`, `00edce20`; B9/B10
  remained unreachable.
- Root cause: verified ownership/selection and stale-attempt failure, not
  duplicate packet IDs.

### PR #675 inconsistent handoff evidence

- Date: 2026-08-30.
- Evidence: [PR #675 review](https://github.com/jacob202/kitty/pull/675#pullrequestreview-5061574624).
- Result: `.claude/STATE.md` and `.claude/HANDOFF.md` disagreed; continuity
  checks failed while 4,819 other tests passed.
- Root cause: verified stale/inconsistent checkpoint content on #675.

### PR #673 stale-SHA acceptance

- Date: 2026-08-30.
- Evidence: [PR #673 review](https://github.com/jacob202/kitty/pull/673#pullrequestreview-5061417894).
- Result: independent running-product acceptance targeted older
  `e6591dc1...` while current reviewed head was `ead4d973...`; exact-head
  acceptance had to be rerun before merge.
- Root cause: verified evidence binding failure; duplicate-ID harm not shown.

### PR #675/#677 overlapping continuity files

- Date: 2026-08-30.
- Evidence: [PR #677 comment](https://github.com/jacob202/kitty/pull/677#issuecomment-5470489074).
- Both PRs touched `.claude/STATE.md`/`.claude/HANDOFF.md`; whoever merged
  second would need a rebase.
- Direct cause of #675's four failures was its inconsistent checkpoint, not
  overlap. Overlap is a verified merge-order risk; any extra rework is
  inference, not measured.

## Required lightweight packet receipt

A packet receipt may be Markdown or the existing runtime-compatible manifest,
but must state:

- one outcome and one owner;
- exact base SHA and approved packet identity;
- exact allowed paths and explicit paths not to touch;
- acceptance criteria with runnable commands;
- final-SHA evidence: changed paths, tests, review identity, and runtime proof
  for runtime claims;
- blockers, unknowns, stop/split condition, and one next action.

Do not add receipt metadata to executable JSON unless the Builder validator
already accepts it. Keep product intent in the mission/roadmap and live state
in Builder.

## LIBRARY-CHAT-001 pilot

### Objective

From the native Library surface, attach one ready local image to a new or
existing Chat message. Supported inputs are PNG, JPEG, and WebP files no
larger than 5 MiB. The user sees ready, sending, sent, and failed states;
retry is explicit and never duplicates a sent attachment.

### Approved implementation paths

Only these paths may change:

- `gateway/kitty-chat/src/components/LibraryView.tsx`
- `gateway/kitty-chat/src/components/ChatMessage.tsx`
- `gateway/kitty-chat/src/components/InputBar.tsx`
- `gateway/kitty-chat/src/lib/chat-client.ts`
- `gateway/kitty-chat/src/lib/gateway.ts`
- `gateway/kitty-chat/src/lib/types.ts`
- `gateway/kitty-chat/src/app/page.tsx`
- `gateway/kitty-chat/src/__tests__/library-chat-001.test.tsx`
- `gateway/routes/chats.py`
- `tests/test_library_chat_001.py`

No other paths are approved.

### Acceptance

1. A ready PNG/JPEG/WebP at or below 5 MiB can be selected in Library and
   appears in Chat before send.
2. Unsupported type or size over 5 MiB is rejected before network dispatch with
   plain-language actionable copy.
3. Send shows one pending state and one durable sent attachment; retry after a
   failed request sends at most one new request.
4. Reload/reopen reads the durable sent attachment; no client-only success is
   shown after reload.
5. Gateway errors are translated at the render boundary; no raw route, status,
   host, or stack trace is visible.
6. Desktop and iPhone-class browser tests cover ready, reject, failure, retry,
   and reload states.
7. Focused backend/frontend tests and `git diff --check` pass.

### Out of scope

PDF/audio/video, image transformation, cloud upload/provider changes, new
ArtifactStore schema, chat history redesign, Library indexing redesign,
Builder changes, credentials, live DB migration, or broad visual polish.

### Validation and evidence

Run the named backend test, the named frontend test, the repository's existing
focused UI command, and `git diff --check`. Record exact output, base and final
SHA, changed paths, and one independent review bound to final SHA. Running-app
proof must cover desktop and iPhone-class widths and a failed network path.

## Guarded Builder improvements

Builder changes are allowed only when a dated flow-break record proves Builder
is the blocker, no verified active owner exists, and Jacob/mission authority
approves a separate bounded change. The change must name exact paths, tests,
owner, base SHA, and stop conditions. Shadow scheduler/queue/execution
authority is forbidden: no second queue, scheduler, lease model, or state
machine may be introduced. Existing Builder code may be repaired when the
flow-break evidence and approval meet these conditions.

## Five-step roadmap

1. **Baseline:** refresh main, mission, ownership, and runtime evidence.
2. **Pilot:** implement and independently accept LIBRARY-CHAT-001.
3. **Flow-break pass:** record only reproducible blockers exposed by the pilot.
4. **Bounded repair:** fix the highest-leverage approved blocker with one owner
   and one packet/PR.
5. **Mission acceptance:** re-run integrated journeys, then decide whether more
   packet tooling is justified by measured friction.

## Before/after workflows

Before: idea or stale handoff → competing packet/spec → unclear owner →
implementation/review on drifting SHA → manual reconstruction after failure.

After: mission outcome → one small receipt with owner/base/allowed paths →
fresh evidence and collision check → bounded implementation → exact-SHA
validation/review/runtime proof → final receipt with one next action.

## Success metrics

- Pilot completion rate: one accepted Library→Chat journey without manual
  reconstruction.
- Truthfulness: zero raw errors, false success, or client-only attachment after
  reload in the acceptance matrix.
- Recovery: failed send has one explicit retry and zero duplicate sends.
- Scope: zero changed paths outside the approved list.
- Efficiency: no second implementation owner and no stale-SHA review accepted.
- Builder escalation quality: every Builder change has a flow-break record and
  explicit approval; otherwise no Builder code changes.

## Optional future tooling

Only if active duplicate friction recurs, add
`scripts/list_packet_ids.py`. It must be read-only, list each packet ID and
source path, and flag duplicates. It must not generate a registry, mutate
manifests, infer status, inspect Builder state, or become a second authority.

## Tiny flow-break record

| Timestamp | Approved packet | Claimed task | Stage | Expected | Observed | Evidence link/SHA | Blocker owner | Decision |
|---|---|---|---|---|---|---|---|---|
| ISO-8601 | ID | task ID | select/claim/run/validate/review/publish | one sentence | one sentence | URL + SHA | person/lane/UNKNOWN | stop/fix/reassign |

## Risks and resume rule

The principal risks are stale evidence, unclear ownership, and overbuilding
control-plane documentation before a user outcome exists. If credits or runtime
capacity stop work, preserve the branch and receipt, record the exact blocker
as UNKNOWN/BLOCKED, and resume by refreshing main, #490, relevant PRs, Builder
projection, and the receipt's base/final identity. Never recreate a packet ID,
claim success from code existence, or silently broaden scope.
