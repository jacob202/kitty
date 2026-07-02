# Packet 001 — State spine: signals, snapshots, /state/now

- **Status:** shipped (implemented in the same PR that introduced this file)
- **Best executor:** Claude Code or Codex
- **Purpose:** Give Kitty a queryable "now" and a mechanical "what changed" —
  the primitive every other spine packet builds on.

## Scope (as shipped)

- `gateway/migrations/007_signals.sql` — `signals` (append-only events with
  UNIQUE `dedupe_key`) + `state_snapshots` (persisted composed state).
- `gateway/signal_store.py` — emit / list_recent / list_unprocessed /
  list_since / count_unprocessed / mark_processed. Payload capped at 16KB
  (summaries and pointers, not blobs). Dedupe hit returns `None`.
- `gateway/state_composer.py` — `compose_now()` fans out to sections
  (todos, inbox, journal, chats, calendar, signals), each bounded by
  `SOURCE_TIMEOUT_SECONDS`; a broken source becomes
  `{"ok": false, "error": ...}`, never a fake empty. `snapshot_now()`
  persists a baseline; `changes_since_snapshot()` returns a mechanical
  scalar diff + signals since the baseline. No LLM anywhere.
- `gateway/routes/state.py` — `GET /state/now`, `POST /state/snapshot`,
  `GET /state/changes`; registered in `routes/register.py`.
- Tests: `tests/test_signal_store.py`, `tests/test_state_composer.py`,
  `tests/test_state_route.py`; migration-list assertion updated in
  `tests/test_db.py`.

## Verification

```bash
python3.12 -m pytest tests/test_signal_store.py tests/test_state_composer.py tests/test_state_route.py -q
python3.12 -m pytest tests/ -q --tb=short
curl -s localhost:8000/state/now | jq .
```

## Known limitations (deliberate, not bugs)

- `calendar_integration.get_today` masks AppleScript failures as an empty
  day; the fix belongs to the calendar module, not the composer.
- Nothing snapshots automatically yet — a cron entry calling
  `POST /state/snapshot` daily is a one-line follow-up once the cadence is
  chosen (morning brief time is the natural moment).
- `_diff_sections` compares scalars only; list contents are display detail.

## Unlocks

Packets 002 (triage consumes signals/inbox), 003 (actions cite a source
signal), 004 (home binds to /state/*), 005+ (connectors emit signals),
and the brief opening with a real "what changed."
