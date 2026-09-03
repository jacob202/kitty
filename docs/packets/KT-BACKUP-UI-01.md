# KT-BACKUP-UI-01 — Backup becomes a real screen

**Initiative:** none — deliberately has no Builder manifest
**Owner:** codex (or an interactive session)
**Depends on:** `KT-RESTORE-01` must be merged first
**Base:** `origin/main` `8cdc8e2e` or later
**Findings:** `XCUT-B003`
**Decision:** `D-014`, confirmed by Jacob as `D-015`

## Why there is no manifest
A Builder worktree is a git worktree and `node_modules/` is gitignored, so it is
absent, and the runner exposes a Python toolchain but no Node one
(`PACKET_STANDARD.md` F9, decision `D-007`). This packet changes only frontend
files, so there is no Tier-1 gate Builder could execute. It goes to a person or
to Codex.

## What Jacob can do after this
Back up his Kitty and restore it, from inside Kitty, without a terminal.

## Why this is the next thing
Jacob settled it on 2026-08-31: *"back up should get a real screen"*.

The backend is already finished and already served over HTTP:

- `gateway/routes/integrations.py:85` — `GET /sync/export` returns
  `storage_sync.export_all()`.
- `gateway/routes/integrations.py:93` — `POST /sync/import` takes a snapshot
  body and returns `{"imported": counts}`.

Grepping `gateway/kitty-chat/src` finds no caller of either. Verified at the
base SHA above.

## Wait for KT-RESTORE-01
Do not ship this screen before `KT-RESTORE-01` is merged. Until it is,
`import_all` **appends** instead of replacing, so a restore button would hand
Jacob three copies of every memory and call it a restore. `KT-RESTORE-01` also
removes the 1000-record export cap; without it, a backup taken from this screen
would silently omit everything past a thousand records.

## Plan
1. Confirm `KT-RESTORE-01` is merged. If it is not, stop.
2. Read `gateway/routes/integrations.py` and `gateway/storage_sync.py` so the
   screen describes what the snapshot actually contains.
3. Add a Backup destination to the view/navigation registry.
4. Back up: one control that calls `GET /sync/export` and saves the snapshot
   where Jacob can find it. Say what it contains and how many records, in
   plain words — "1,240 memories, 88 journal entries", not a JSON dump.
5. Restore: pick a snapshot, show what is in it and what it will replace, then
   call `POST /sync/import` and report the counts it returned. Restoring
   replaces; say so on the screen before he presses it.
6. Failure is a first-class state. If the gateway rejects the snapshot, show
   the reason it gave. Never show a raw status code — the
   `ArtifactChatRejection` pattern in `gateway/kitty-chat/src/lib/gateway.ts`
   is the precedent for surfacing the gateway's own `detail` string.
7. Every control does its thing in place. A card that only reports the date of
   the last backup is a defect, not a feature.
8. Check at an iPhone-class width: no horizontal overflow, no control under the
   tab bar.

## Not in scope
Scheduling automatic backups. Cloud or off-machine storage — this is local
only. Changing the snapshot format or its version check. Anything in
`gateway/storage_sync.py`; if the screen needs a backend change, that is a
separate packet.

## Verification
**Tier 1 — mechanical.** Not available to Builder. For Codex or a person:
`cd gateway/kitty-chat && npx vitest run tests/BackupView.test.tsx --reporter=dot`
and `npx tsc --noEmit`. The tests must cover: export renders the record counts
the gateway returned; import reports the counts the gateway returned; a
rejected import shows the gateway's own reason and never a bare status code.

**Tier 2 — running app.** A spec under `gateway/kitty-chat/tests/smoke/` that
reaches the Backup screen at both `desktop` and `mobile` projects, exports, and
shows a rejection in plain language. Route-stub the gateway; never call the
real `/sync/import` from a smoke test.

**Tier 3 — product acceptance.** Required (D-008), and it matters here because
a wrong result destroys data. An independent reviewer, on the running product:
take a backup, add a memory, restore the backup, and confirm the added memory
is gone and nothing is duplicated.

## Stop condition
If the screen cannot describe what a snapshot contains without a backend
change, stop and say so. Do not invent counts.

## Recovery
Frontend only; nothing here is destructive to the repository. Never point a
test at the real Kitty database — use a temporary data root.
