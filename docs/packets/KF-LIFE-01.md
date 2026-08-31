# KF-LIFE-01 — Life awareness distinguishes an empty calendar from an unavailable one

**Initiative:** `kitty-opens-the-doors-20260831-v3`
**Owner:** builder
**Free or paid:** free
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`

## Outcome boundary
Backend-only packet. Frontend visibility/actionability is owned by its manifest-less interactive companion.

## Current finding
today_events() maps calendar unavailable to [], and today_summary/DND/morning projections currently have no source-health field, so unavailable and genuinely empty are observationally identical.

## Objective
gateway/life_awareness.py today_events() intentionally returns a list and currently returns [] both when the calendar is available with zero events and when calendar_integration.is_available() is false. Preserve today_events() compatibility, but add one bounded source-health seam so today_summary(), do_not_disturb_status(), and morning_proactive() carry explicit calendar availability/state alongside the existing events/event_count fields. Update gateway/routes/life.py only as needed so /life/check exposes that same truth. Do not infer that the user is free merely because the calendar source is unavailable; existing booleans may remain for compatibility only when accompanied by explicit availability metadata. Do not add a store, migration, scheduler, provider, or frontend change. This packet creates no new files.

## Acceptance
- When calendar integration is available and returns no events, life projections report calendar available/healthy and event_count 0.
- When calendar integration is unavailable, life projections explicitly report the calendar source unavailable/degraded instead of presenting the empty event list as healthy truth.
- today_events() remains a list-returning compatibility API for existing callers.
- do_not_disturb_status(), today_summary(), and morning_proactive() expose the same calendar source truth; /life/check carries it through without fabricating an event or meeting.
- Existing meeting detection, life-step suggestions, cache invalidation, and generated-text fallbacks remain compatible.
- python -m pytest -q tests/test_life_awareness.py passes.

## Verification
- `python -m pytest -q tests/test_life_awareness.py`
- `python -m ruff check gateway/life_awareness.py gateway/routes/life.py tests/test_life_awareness.py`

Existing green tests are only a baseline; the worker must add a regression for the missing behavior before production edits.

## Stop condition
If truthful source state requires changing calendar_integration itself, app.py, life_cron.py, or a frontend surface, stop and report that dependency instead.

## Recovery
Read/projection contract plus tests only; no durable product data changes.
