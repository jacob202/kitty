# Phase C3 Plan — Cron Schedules DB Consolidation

**Date:** 2026-07-06

## Goal

Move `gateway/cron.py`'s standalone `data/cron_schedules.db` into the shared
`data/kitty/kitty.db` so all app-owned episodic state lives in one place,
and `kitty backup` picks up cron state without any new backup code.

## Why this is high-risk

The cron runner is a background asyncio task that polls every 30 seconds and
writes `last_run` back to the DB on each fire. If it writes to the old DB
while the import is reading it, `last_run` values diverge. The fix is:
**stop the runner, migrate atomically, restart**. Never migrate while Kitty
is running.

## Current state

- `gateway/cron.py` owns `data/cron_schedules.db` — one table `schedules`.
- As of 2026-07-06 the table is empty (0 rows). The dry-run protocol below
  covers the non-empty case for future operators.
- `data/cron_schedules.db` is **not** in the `kitty backup` path.
- `gateway/db.py` manages all migrations into `data/kitty/kitty.db`.
- Next migration slot: **012**.

## Non-Goals

- No changes to the cron scheduling logic or API.
- No migration of `autonomy_state.db` (separate risk profile, different plan).
- No deletion of `data/cron_schedules.db` — left intact as rollback source.
- No changes to the `/cron` route API contract.

## Scope

One table: `schedules` → `cron_schedules` in `kitty.db`.

The rename (`schedules` → `cron_schedules`) avoids any future collision in
the shared DB. Only `gateway/cron.py` references this table.

---

## Sequence

### C3-0 — Dry Run (run BEFORE any code changes)

This verifies that the migration logic is correct on a copy of real data
before touching the live DB.

```bash
# 1. Stop Kitty (required — kills the 30s background writer)
./kitty down

# 2. Snapshot both DBs
sqlite3 data/cron_schedules.db ".dump" > /tmp/cron_pre.sql
cp data/cron_schedules.db /tmp/cron_pre.db
cp data/kitty/kitty.db /tmp/kitty_pre.db

# 3. Verify source row count
sqlite3 /tmp/cron_pre.db "SELECT COUNT(*) FROM schedules;"
# → record this number as EXPECTED_ROWS

# 4. Apply migration to the COPY only
sqlite3 /tmp/kitty_pre.db < gateway/migrations/012_cron_schedules.sql
python3.12 scripts/dry_run_c3.py --src /tmp/cron_pre.db --dst /tmp/kitty_pre.db

# 5. Verify destination
sqlite3 /tmp/kitty_pre.db "SELECT COUNT(*) FROM cron_schedules;"
# → must equal EXPECTED_ROWS

# 6. Diff spot-check (all columns must match)
sqlite3 /tmp/cron_pre.db "SELECT id, name, action, schedule_type, schedule_value, enabled, last_run, metadata FROM schedules ORDER BY id;" > /tmp/src_rows.txt
sqlite3 /tmp/kitty_pre.db "SELECT id, name, action, schedule_type, schedule_value, enabled, last_run, metadata FROM cron_schedules ORDER BY id;" > /tmp/dst_rows.txt
diff /tmp/src_rows.txt /tmp/dst_rows.txt
# → must be empty diff

# 7. Sign off: if diff is empty and counts match, proceed to C3-1.
#    If not, fix the migration script before touching live data.
```

The dry-run script (`scripts/dry_run_c3.py`) is a 20-line helper that reads
the source table and inserts rows into the destination. Discard it after
the live run.

---

### C3-1 — Schema Migration

File: `gateway/migrations/012_cron_schedules.sql`

```sql
CREATE TABLE IF NOT EXISTS cron_schedules (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    action        TEXT NOT NULL,
    schedule_type TEXT NOT NULL,
    schedule_value TEXT NOT NULL,
    metadata      TEXT DEFAULT '{}',
    enabled       INTEGER DEFAULT 1,
    last_run      REAL DEFAULT 0,
    created_at    REAL
);
```

Tests:

- Open a fresh in-memory DB, run all migrations through 012, assert
  `cron_schedules` table exists.
- Assert the existing 11 tables (`schema_migrations`, `app_settings`,
  `plugin_settings`, `todos`, `chats`, `journal_entries`, `buddy_state`,
  `signals`, `inbox_triage`, `actions`, `projects`, `project_next_steps`)
  are untouched.

---

### C3-2 — Update `gateway/cron.py`

Changes:

1. Remove `CRON_DB = DATA_DIR / "cron_schedules.db"`.
2. Import `KITTY_DB_FILE` from `gateway.paths` and `connect` from
   `gateway.db` (already used by all other stores).
3. Replace all `sqlite3.connect(CRON_DB)` with `kitty_db.connect(KITTY_DB_FILE)`.
4. Rename table from `schedules` to `cron_schedules` in all queries.
5. Add `_import_legacy_cron_once()` — same pattern as `todo_store`,
   `chats_store`, `journal_store`, `buddy_store`:
   - If `cron_schedules` table is empty **and** `data/cron_schedules.db` exists,
     copy rows over.
   - Mark done via `app_settings` key `cron_legacy_imported`.
   - Never deletes the source file.
6. Call `_import_legacy_cron_once()` at the top of `init_db()`.

The `CREATE TABLE IF NOT EXISTS` block inside `init_db()` can be removed;
migration 012 owns the schema.

Tests (add to `tests/test_cron.py`):

- `test_schedule_round_trip` — schedule → list → assert row present.
- `test_remove` — schedule → remove → list → assert absent.
- `test_toggle` — schedule → toggle → assert enabled flipped.
- `test_update` — schedule → update → list → assert new values.
- `test_legacy_import_copies_rows` — write rows to a temp `cron_schedules.db`,
  point `cron.LEGACY_CRON_DB` at it, call `_import_legacy_cron_once()`,
  assert rows appear in `kitty.db` copy.
- `test_legacy_import_is_idempotent` — run import twice, assert row count
  unchanged.
- `test_rollback_re_imports_from_intact_db` — drop `cron_schedules` table,
  delete `cron_legacy_imported` setting, re-run `init_db()`, assert rows
  re-imported from still-present source file.

---

### C3-3 — Live Migration Run

```bash
# 1. Stop Kitty
./kitty down

# 2. Final snapshot (insurance)
sqlite3 data/cron_schedules.db ".dump" > data/backups/cron_pre_c3_$(date +%Y%m%d_%H%M%S).sql

# 3. Start Kitty — init_db() fires _import_legacy_cron_once() on first request
./kitty up

# 4. Verify
./kitty doctor --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('cron', 'not found'))"
sqlite3 data/kitty/kitty.db "SELECT COUNT(*) FROM cron_schedules;"
# → must match the row count from the dry-run baseline

# 5. Verify backup picks up cron state
./kitty backup
ls data/backups/kitty/  # new backup dir should exist
```

---

### C3-4 — Cleanup (after 1 week of stable operation)

- Delete `data/cron_schedules.db` (the legacy source file).
- Remove the `_import_legacy_cron_once()` function from `cron.py`.
- Remove the `cron_legacy_imported` app_setting check.

Do not do this in the same PR as C3-1/2. Let it run for a week first.

---

## Rollback Plan

```bash
# 1. Stop Kitty
./kitty down

# 2. Revert cron.py to use old path
#    - Restore CRON_DB = DATA_DIR / "cron_schedules.db"
#    - Revert table name from cron_schedules → schedules
#    - Remove _import_legacy_cron_once() call

# 3. Restart
./kitty up
```

**Why this is safe:** `data/cron_schedules.db` is never deleted. Worst case
on rollback after a fire: one schedule's `last_run` was updated in the new DB
but not the old → that schedule fires once more than intended on the next run.
On a single-user system, acceptable.

---

## Acceptance Criteria

- [ ] Dry-run produces empty diff (C3-0 signed off before C3-1 PR opens).
- [ ] Migration 012 runs on a fresh DB without touching existing tables.
- [ ] `gateway/cron.py` makes zero references to `data/cron_schedules.db` path.
- [ ] All cron tests pass (schedule, list, remove, toggle, update, import, idempotent, rollback).
- [ ] `./kitty doctor --json` shows cron state healthy after live run.
- [ ] `./kitty backup` includes `kitty.db` with `cron_schedules` table.
- [ ] `data/cron_schedules.db` still exists (not deleted).

---

## Out of Scope / Deferred

| Item                     | Why deferred                                                                                    |
| ------------------------ | ----------------------------------------------------------------------------------------------- |
| `data/autonomy_state.db` | Different risk profile (1MB, 2 related tables, active during autonomy runs); needs its own plan |
| `data/todos.db`          | Already migrated; legacy file kept per policy                                                   |
| `data/model_digest.db`   | Explicitly deferred in STORAGE_MIGRATION_PLAN.md ("leave until shared DB proven")               |

---

## Risk Profile

- **Data volume:** 0 rows today. The protocol handles the non-empty case.
- **Concurrency:** background writer eliminated by `./kitty down` before migration.
- **Schema complexity:** single table, no foreign keys, no cross-store references.
- **Rollback window:** old file never deleted; revert is one `cron.py` change + restart.
- **Overall:** Medium. Rated high due to live writer hazard; mitigated by hard stop/start requirement.
