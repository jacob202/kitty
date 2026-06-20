# Phase B Plan - One Storage Story

**Date:** 2026-06-20

## Goal

Make Kitty's app-owned state understandable, testable, and backup-friendly without changing the user experience.

## Non-Goals

- No cloud sync.
- No mobile app.
- No new agent dashboard.
- No ChromaDB or mem0 migration.
- No broad rewrite of `llm_client.py`.
- No schema work that requires deleting user data.

## Sequence

### B0 - Baseline And Guardrails

- Run the default pytest suite and record the real result.
- Confirm `./kitty doctor --json` behavior.
- Add tests around any store before migrating it.

### B1 - SQLite Foundation

- Add one gateway-owned DB module.
- Store schema migrations under a predictable path.
- Define the DB path in `gateway/paths.py`.
- Tests: open DB, run migrations, fail loudly on migration error.

### B2 - First Low-Risk Store

- Migrate one small app-owned store first, preferably plugin settings or another non-chat store.
- Keep the public route/API unchanged.
- Add an import/backup path that never deletes the old file automatically.

### B3 - User-Facing Episodic Stores

- Migrate chats, todos, loops, nudges, and buddy state only after B2 proves the seam.
- Keep old files readable during transition.
- Emit explicit migration errors with file path and schema version.

### B4 - Write-Side Storage Router

- Add a small write API that mirrors the existing `memory_graph` read rule.
- Do not hide write failures.
- Route modules should stop importing store internals directly as they migrate.

### B5 - Backup And Restore Drill

- Add a local backup command for `data/kitty/`.
- Prove restore into a temporary directory.
- Document exactly what is and is not backed up.

## Acceptance Criteria

- A fresh checkout can run migrations without manual path edits.
- No user data is deleted by migration scripts.
- Tests cover migration success and failure.
- Docs and code agree on the current storage story.
- Future mobile capture can still append to `data/inbox.jsonl`.
