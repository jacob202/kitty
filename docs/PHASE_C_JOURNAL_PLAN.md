# Phase C B Plan - Migrate Journal

**Date:** 2026-06-20

## Goal

Move journal entry storage from a single JSONL file behind the same
seam as todos, plugin settings, and chats. Adds `journal_entries` to
the Phase B backup story and keeps the storage surface uniform.

## Non-Goals

- No ChromaDB or mem0 migration.
- No journal search or ranking changes.
- No schema work that requires deleting user data.
- No changes to the journal route API contract.
- No interview mode or prompt changes (the user's recent work is
  committed and is not in scope for this migration).
- No migration of the stale `data/journal.schema.sql` file (it's a
  prior-design artifact that doesn't match the current data shape).

## Current State

- `gateway/journal.py:23` (`save_journal_entry`) writes to
  `DATA_DIR / "journal_entries.jsonl"` (JSONL append). The record
  shape is `{ts: float, theme: str|None, entry: str, session_id?: str}`.
- `gateway/routes/journal.py` exposes 3 routes: `GET /journal/prompt`,
  `POST /journal/start`, `POST /journal/synthesize`. None of them
  write to storage directly; the actual writes happen inside
  `save_journal_entry`.
- `data/journal_entries.jsonl` does not currently exist on this
  machine — no journal entries have been persisted yet.
- `data/journal.schema.sql` is a stale schema file from a prior
  design (columns: `id, timestamp, role, content, content_hash`).
  The actual data shape from `save_journal_entry` is different
  (`ts, theme, entry, session_id`), so we ignore the old schema.
- `gateway/chats_store.py` (Phase C, ships at `e6a5712`) is the
  model for the read/write module and the one-time import.

## Sequence

### B0 - Plan (this document)

### B1 - Schema

- Add migration `gateway/migrations/005_journal_entries.sql` with
  the `journal_entries` table.
- Columns: `id INTEGER PK AUTOINCREMENT`, `ts REAL NOT NULL`,
  `theme TEXT`, `entry TEXT NOT NULL`, `session_id TEXT`,
  `created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`.
- Use normalized columns (not a JSON blob) because the journal shape
  is stable and reads are common (`list_entries`, `count_entries`).
- Tests: open DB, run migrations. Verify `chats` and
  `journal_entries` both exist; verify the existing tables are
  untouched.

### B2 - Read/Write Module

- Add `gateway/journal_store.py` with:
  - `append_entry(ts, theme, entry, session_id=None) -> dict` —
    mirrors `save_journal_entry`'s return shape
  - `list_entries(limit=50, theme=None) -> list[dict]` — newest first
  - `count_entries(theme=None) -> int`
- Backed by SQLite via `gateway/db.py`.
- Tests: round-trip an entry, query by theme, count, ordering.

### B3 - Module/Routes Migration

- Modify `gateway/journal.py:save_journal_entry` to call
  `journal_store.append_entry` instead of writing to the JSONL file.
- The route module (`gateway/routes/journal.py`) does not write to
  storage directly, so no route changes are needed. It calls
  `save_journal_entry` which now writes through the store.
- Tests: integration test that `save_journal_entry` round-trips
  through SQLite.

### B4 - Backward Compat (one-time import)

- On first call to `append_entry` / `list_entries`, if the
  `journal_entries` table is empty AND `data/journal_entries.jsonl`
  exists, import each line into the table.
- After import, the JSONL file is left intact (no auto-deletion).
- The import marker is stored in `app_settings` under
  `journal_legacy_imported`, with the outcome recorded as the value.
- Tests: import path with non-empty JSONL; empty-table + missing
  JSONL path; import-already-done path (no double-import).

### B5 - Backup Verification

- After B1, `journal_entries` is part of `kitty.db`, so the SQLite
  backup API picks it up automatically. Verification only — no new
  backup code.

### B6 - Rollback Plan

- **If B1–B3 fail to land:** revert in one commit. `DROP TABLE
  journal_entries;` and revert `save_journal_entry` to write JSONL.
- **If B4's import runs but later proves wrong:** delete the table
  contents and re-import from the still-intact JSONL file.
- **Rollback procedure (documented escape hatch):**
  1. `DROP TABLE journal_entries;`
  2. `DELETE FROM app_settings WHERE key = 'journal_legacy_imported';`
  3. `DELETE FROM schema_migrations WHERE name = '005_journal_entries.sql';`
  4. Re-run the gateway; migrate re-applies 005_journal_entries.sql
     and the import rebuilds the table from the JSONL file.
- **Rollback test:** mirrors `chats_store`'s C6 test — write a
  JSONL file, import it, drop the table + both markers, verify the
  next read re-imports from the JSONL file.

## Acceptance Criteria

- No user data is deleted by the migration.
- Tests cover import, round-trip, and rollback paths.
- The journal route API contract is unchanged from the client
  perspective.
- The Phase B backup picks up journal entries automatically.
- Rollback is one revert away, and the rollback test passes.

## Out of Scope (deferred to later phases)

- ChromaDB-based journal search.
- Journal analysis, clustering, or theme extraction.
- Migrating the stale `data/journal.schema.sql` file.
- Multi-device journal sync.

## Risk Profile

- **Low:** single-user, no concurrent writers, small data volume.
- **Low:** no foreign keys, no cross-store references.
- **Low:** the existing `save_journal_entry` is append-only; the
  store mirrors that.
- **Negligible:** no legacy data on this machine, so import is empty
  by default. Rollback only matters if a future operator has
  `journal_entries.jsonl` from a different instance.
- **Medium:** the existing `data/journal.schema.sql` is stale. We
  ignore it; future agents might be confused. The plan documents
  this explicitly.
