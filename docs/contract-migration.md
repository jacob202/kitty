# Contract-first migration ledger

Goal: every gateway route returns a typed Pydantic response model, the OpenAPI
schema generates the TypeScript client, and `gateway/kitty-chat/src/lib/gateway.ts`
stops carrying hand-written response shapes.

Branch: `contract-first`. Update this file as the **last action of every work slice**.

## How to resume

```bash
cd gateway/kitty-chat && npm run gen:api-types   # regenerate types (no server needed)
npx tsc --noEmit                                  # typecheck
node node_modules/next/dist/bin/next build        # must pass at every commit
```

Then pick the next `pending` route file below, smallest first.

## Pipeline (proved 2026-07-25)

`gateway/routes/*.py` (Pydantic `response_model=`)
→ `scripts/dump_openapi.py` (imports `gateway.app`, writes `src/lib/gen/openapi.json`)
→ `openapi-typescript` → `src/lib/gen/gateway-schema.d.ts`
→ `gateway.ts` imports `components['schemas'][...]`

Both generated files are committed. Generation is deterministic — regenerating
with no backend change produces byte-identical output, so any diff in
`openapi.json` is a real contract change and reviewable as such.

## Status

204 routes across 48 files with routes (50 files in `gateway/routes/`, 2 have none).
3 routes have a `response_model` today.

Legend: **done** = response model + gateway.ts consuming the generated type.
**partial** = model exists, gateway.ts not yet migrated.

| Route file | Routes | response_model | Has BaseModel | Status |
|---|---:|---:|---|---|
| capture.py | 2 | 2 | yes | **done** (`CaptureResult` → `CaptureResponse`) |
| knowledge.py | 5 | 1 | yes | **partial** — see D-002 (BLOCKED on decision) |
| extended.py | 36 | 0 | yes | pending |
| integrations.py | 24 | 0 | yes | pending |
| life.py | 12 | 0 | no | pending |
| projects.py | 8 | 0 | yes | pending |
| experts.py | 7 | 0 | yes | pending |
| kitty_tools.py | 7 | 0 | yes | pending |
| tutor.py | 7 | 0 | yes | pending |
| chats.py | 6 | 0 | no | pending |
| cron.py | 6 | 0 | yes | pending |
| actions.py | 5 | 0 | yes | pending |
| journal.py | 5 | 0 | yes | pending |
| completions.py | 4 | 0 | yes | pending |
| deadlines.py | 4 | 0 | no | pending |
| idea_mine.py | 4 | 0 | no | pending |
| loops.py | 4 | 0 | no | pending |
| monitors.py | 4 | 0 | no | pending |
| calendar.py | 3 | 0 | yes | pending |
| desktop.py | 3 | 0 | yes | pending |
| dream.py | 3 | 0 | no | pending |
| feedback.py | 3 | 0 | no | pending |
| repairs.py | 3 | 0 | no | pending |
| runtime.py | 3 | 0 | yes | pending |
| state.py | 3 | 0 | no | pending |
| artifacts.py | 2 | 0 | no | pending |
| brief.py | 2 | 0 | no | pending |
| inbox.py | 2 | 0 | no | pending |
| insights.py | 2 | 0 | no | pending |
| memories.py | 2 | 0 | no | pending |
| onboarding.py | 2 | 0 | no | pending |
| perf.py | 2 | 0 | no | pending |
| personality.py | 2 | 0 | yes | pending |
| telos.py | 2 | 0 | yes | pending |
| voice.py | 2 | 0 | yes | pending |
| ask.py | 1 | 0 | yes | pending |
| builder_control.py | 1 | 0 | yes | pending |
| council.py | 1 | 0 | yes | pending |
| import_chatgpt.py | 1 | 0 | no | pending |
| logs.py | 1 | 0 | no | pending |
| magic.py | 1 | 0 | no | pending |
| network.py | 1 | 0 | no | pending |
| prompts.py | 1 | 0 | no | pending |
| search.py | 1 | 0 | no | pending |
| session_context.py | 1 | 0 | no | pending |
| signals.py | 1 | 0 | no | pending |
| status.py | 1 | 0 | no | pending |
| usage.py | 1 | 0 | no | pending |

## Contradictions found (backend vs gateway.ts)

Live disagreements between what the handler returns and what the TS client
expects. Each is a potential runtime bug. **Not silently resolved.**

### C-001 — `/knowledge/ingest` status type

- Backend `IngestResponse.status` is `str` (`gateway/routes/knowledge.py:77`).
- `gateway.ts` `KnowledgeIngestResult.status` is `'success' | 'skipped' | 'failed' | 'pending'`.
- **Reality**: the handler clamps to exactly those four values via
  `ALLOWED_STATUSES` (`knowledge.py:29,148`) on every return path, including the
  exception path. The TS union is *correct*; the Pydantic model is the imprecise side.
- **Resolution**: narrow the Pydantic field to
  `Literal["success","skipped","failed","pending"]`. This is narrowing to match
  reality, not widening, and changes no runtime behaviour (the clamp already exists).
- Deferred out of Phase 0 to keep the proving loop to one call site. Do this first
  in the knowledge.py slice.

## Deletion candidates

Fields a route returns that nothing in `gateway.ts` consumes. **Flagged only —
do not delete in this campaign.**

*(none yet)*

## Decisions log

### D-001 — Dump OpenAPI by import, not from a live server (2026-07-25)

`src/lib/gen/README.md` (Jul 14) specified `openapi-typescript
http://127.0.0.1:8000/openapi.json`, requiring a running gateway.

Changed to `scripts/dump_openapi.py`, which imports `gateway.app` and writes the
schema offline. Reasons:

1. **CI can't boot the gateway**, so the README's loop could never be verified in
   CI — and "CI green" is a stated requirement of this campaign.
2. **A running server is a stale-build hazard**: curling :8000 generates types
   from whatever code that process started with, not the working tree.
3. Deterministic output makes the committed `openapi.json` a meaningful diff.

The README's *intent* — pull types from OpenAPI instead of hand-maintaining them
— is unchanged and correct. Only the mechanism changed. README updated to match.

### D-002 — `/knowledge/ingest` left partial in Phase 0 (2026-07-25)

Phase 0 said prove the loop on one call site and don't expand. `CaptureResult`
matched `CaptureResponse` field-for-field, so it was the zero-risk migration.
Migrating `KnowledgeIngestResult` as-is would have *widened* the TS union to
`string` — banned by the campaign's hard rules. See C-001 for the fix.

### D-003 — Migration style: re-export, don't redeclare (2026-07-25)

Hand-written interfaces are replaced with a type alias to the generated schema,
keeping the existing exported name so call sites don't churn:

```ts
export type CaptureResult = components['schemas']['CaptureResponse']
```

Keeps the diff to the type declaration and leaves consumers untouched.

### D-004 — Work in a dedicated worktree, not the shared checkout (2026-07-25)

This campaign runs in `/Users/jacobbrizinski/Projects/kitty-contract-first`
(worktree, branch `contract-first`), **not** in `~/Projects/kitty`.

Mid-Phase-0, a concurrent agent session in the shared checkout checked out
`main`, swept this campaign's uncommitted edits into `stash@{0}`, and committed
its own work onto the `contract-first` branch. Phase 0 had to be reconstructed
from that stash.

A multi-session campaign cannot survive another writer in the same working tree.
Resume work in the worktree above. Verify with `git -C <worktree> branch
--show-current` before starting a slice.

Note: `stash@{0}` is **shared** — it also holds the other session's
`builder_identity.py` and `.claude/` changes. Do not drop it.

## Known-contested files

`.claude/STATE.md` and `.claude/HANDOFF.md` are actively written by other
sessions. This campaign does not touch them; its state lives in this ledger.

## Checkpoint log

- **2026-07-25 — Phase 0 complete.** Pipeline proved end-to-end, loop run twice
  with byte-identical output. 1 route file done (capture.py, 2 routes), 1
  contradiction found (C-001). `next build` green, `tsc --noEmit` clean, 267
  vitest tests pass.
