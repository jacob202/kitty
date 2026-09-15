# Phase C Plan - Migrate Chats

**Date:** 2026-06-20

## Goal

Move chat session storage from a single JSON file behind the same seam
as todos and plugin settings, so chat history is part of the Phase B
backup story and the storage surface is uniform.

## Non-Goals

- No ChromaDB or mem0 migration.
- No multi-user chat.
- No chat search or ranking changes.
- No schema work that requires deleting user data.
- No changes to the `/chats` API contract.

## Current State

- `gateway/routes/chats.py` reads/writes `data/kitty/chats.json` (single JSON file).
- 3 routes: `GET /chats`, `POST /chats`, `DELETE /chats/{chat_id}`.
- `data/kitty/chats.json` does not currently exist on this machine — no chats
  have been persisted yet, so there is no legacy data to import.
- `gateway/storage_router.py` (B4) does not cover chats; only todo + plugin writes.
- `scripts/kitty_backup.py` (B5) backs up `data/kitty/`, so once chats live in
  `kitty.db` they are picked up by the SQLite backup API automatically.

## Sequence

### C0 - Plan (this document)

### C1 - Schema

- Add migration `gateway/migrations/004_chats.sql` with the `chats` table.
- Chat payloads are stored as a JSON blob keyed by `id` to keep the route API
  shape-agnostic.
- Tests: open DB, run migrations, fail loudly on migration error. Verify the
  existing 3 tables (`schema_migrations`, `app_settings`, `plugin_settings`,
  `todos`) are untouched.

### C2 - Read/Write Module

- Add `gateway/chats_store.py` with the same shape as `gateway/todo_store.py`:
  - `list_chats() -> list[dict]`
  - `upsert_chat(chat: dict) -> None`
  - `delete_chat(chat_id: str) -> None`
- Backed by SQLite via `gateway/db.py`.
- Tests: round-trip a chat through the module; id-keyed upsert + delete.

### C3 - Route Migration

- Modify `gateway/routes/chats.py` to call `chats_store` instead of reading
  and writing the JSON file.
- API contract unchanged: same paths, same request/response shapes.
- Tests: integration test that `POST /chats` then `GET /chats` round-trips
  through SQLite. End-to-end test of the same path through FastAPI TestClient.

### C4 - Backward Compat (one-time import)

- On first read, if the `chats` table is empty AND `data/kitty/chats.json`
  exists, import the JSON contents into SQLite. After import, the JSON file
  is left intact (no auto-deletion).
- Tests: import path with non-empty JSON; empty-table + missing-JSON path;
  import-already-done path (no double-import).

### C5 - Backup Verification

- `scripts/kitty_backup.py` already backs up `data/kitty/`, and the `chats`
  table is part of `kitty.db` after C1, so the SQLite backup API picks it up
  automatically. Verification only — no new backup code.

### C6 - Rollback Plan

- **If C1-C3 fail to land:** revert in one commit. The `chats` table can be
  dropped via `DROP TABLE chats;` and the route reverted to JSON.
- **If C4's import runs but later proves wrong:** delete the `chats` table
  contents and re-import from the still-intact JSON file.
- **Rollback test:** a test that simulates a broken migration and verifies
  the route can fall back to reading the JSON file. This is the documented
  escape hatch and the only way we can claim "rollback works."
- The migration is small enough to revert in one commit; the JSON file is
  never deleted, so the user-visible data shape never disappears.

## Acceptance Criteria

- No user data is deleted by the migration.
- Tests cover import, round-trip, and rollback paths.
- The `/chats` API contract is unchanged from the client perspective.
- The Phase B backup picks up chat history automatically (no new backup code).
- Rollback is one revert away.
- The `chats` table is part of `data/kitty/kitty.db` and visible to
  `scripts/kitty_backup.py` without code changes there.

## Out of Scope (deferred to later phases)

- ChromaDB-based chat search.
- mem0 chat embeddings.
- Multi-device chat sync.
- Chat search ranking.
- Migrating journal (Phase C B — second user-facing store, smaller scope,
  lower risk; planned after chats lands).

## Risk Profile

- **Low:** single-user, no concurrent writers, small data volume.
- **Low:** no foreign keys, no cross-store references.
- **Medium:** route is a complete-overwrite pattern today, so the migration
  must keep the "last write wins" semantic.
- **Negligible:** no legacy data on this machine, so import is empty by
  default. Rollback only matters if a future operator has chats.json from
  a different instance.
