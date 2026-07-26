# Project Status

**Verified:** 2026-07-26 against `origin/main` at
`4a0a4c3da72c97df619c0c45ad76426fb645fb52`
**Canonical repo:** `/Users/jacobbrizinski/Projects/kitty`

Branch, worktree, dirty state, relation to `origin/main`, and local Builder state
must be derived from `./kitty context --agent` and supported Builder commands.
They are not copied into this document as live facts.

## What's shipped

Kitty has substantial working product and delivery infrastructure. Verified
shipped areas include:

- consolidated SQLite-backed storage for core state, chats, and journal;
- chat, brief, memory, settings, projects/resume, next-step, phone, image, and
  Builder investigation surfaces;
- durable Builder queue, attempts, leases, validation, recovery rails, worker
  identity checks, initiative tooling, operator controls, and PR publication;
- CI gates for Python, typing, lint, hygiene, frontend tests/build, and browser
  smoke.

This list is a capability summary, not permission to replay historical packets.
Remaining work must be calculated from current code and evidence.

## Current release and open work

PR #264 restored clean-checkout Python and frontend installation and merged to
`main`. Its final required checks passed: dependency install, full pytest with
coverage, frontend tests, production build, browser smoke, lint, mypy, hygiene,
PR description, and independent PR-agent review.

Open governance/manifest work:

- PR #261 — reviewed KittyBuilder Brain research plus manifest-validator checks;
- PR #262 — mechanical repair of 33 initiative validation gates;
- PR #263 — KTF-001 mission, one canonical roadmap, authority alignment, ADR
  amendments, and packet/autonomy policy.

Their live state must be read from GitHub, not inferred from this paragraph.

## Builder state

The Builder database and execution evidence are local runtime state. They were
not available through the GitHub-only verification used for this update, so the
current queue, initiative, attempt, lease, and provider-exhaustion state is
**unknown here**. Use supported `./kitty builder ... --json` projections on the
canonical machine before making a runtime claim.

## Current mission and priority

The approved mission is KTF-001 in `docs/ACTIVE_MISSION.md`. The only active
sequence is `docs/ROADMAP.md` Phase 1:

1. resolve PRs #261, #262, and #263 coherently;
2. reconcile active authority/checkpoint contradictions;
3. calculate the exact remaining Builder reliability delta;
4. author at least two falsifiable `free-exec` JSON packets;
5. inspect one daylight unattended delivery run end to end;
6. prove one real life-project resume loop.

Do not start another feature lane, queue, scheduler, state store, orchestrator,
architecture survey, Builder cockpit, or memory substrate before the Phase 1
exit criteria are met.

## Known limitations

- No existing prose packet is automatically proven `free-exec`.
- Packet 007 emits Markdown drafts, not executable Builder manifests.
- The current nightly drain does not yet prove cross-initiative continuation,
  explicit resumable provider exhaustion, or the complete draft/ready/low-risk
  merge lifecycle.
- Builder runtime recovery and one real resume-loop outcome remain unproven by
  current repository evidence.

Authority routing lives only in `docs/AUTHORITY_MAP.md`; current priority lives
only in `docs/ROADMAP.md` and the approved Mission.
