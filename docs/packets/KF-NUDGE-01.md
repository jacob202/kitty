# KF-NUDGE-01 — Nudges distinguish healthy silence from detector failure

**Initiative:** `kitty-opens-the-doors-20260831-v3`
**Owner:** builder
**Free or paid:** free
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`

## Outcome boundary
Backend-only packet. Frontend visibility/actionability is owned by its manifest-less interactive companion.

## Current finding
All three nudge detector paths collapse internal exceptions to [], so check() and GET /nudges cannot tell healthy silence from partial detector failure.

## Objective
gateway/nudge.py check() is a widely used list-returning API, but each detector catches exceptions and returns [], making detector failure indistinguishable from no applicable nudges. Preserve check() and get_pending() compatibility for app/context callers. Add a bounded status/projection API that runs the same detectors while reporting per-source failure/degradation without fabricating nudges, then have GET /nudges in gateway/routes/integrations.py return that truthful status while retaining the existing nudges key. Dismissal semantics and deterministic nudge ids must remain unchanged. Do not add a store, migration, scheduler, provider, or frontend change. This packet creates no new files.

## Acceptance
- Healthy detectors with no applicable nudges produce nudges: [] and an explicitly healthy source status.
- If one detector fails, healthy detector results are still returned and the response identifies the failed/degraded detector rather than claiming healthy emptiness.
- check() and get_pending() remain list-returning compatibility APIs for existing app and context-enrichment callers.
- GET /nudges retains a nudges key and adds bounded degradation/error metadata sourced from the nudge engine.
- Dismissed nudges remain filtered, deterministic ids remain stable, and detector failure never creates a fake nudge.
- python -m pytest -q tests/test_nudge.py tests/test_integrations_routes.py tests/test_signals_emitters.py passes.

## Verification
- `python -m pytest -q tests/test_nudge.py tests/test_integrations_routes.py tests/test_signals_emitters.py`
- `python -m ruff check gateway/nudge.py gateway/routes/integrations.py tests/test_nudge.py tests/test_integrations_routes.py tests/test_signals_emitters.py`

Existing green tests are only a baseline; the worker must add a regression for the missing behavior before production edits.

## Stop condition
If source health requires changing app startup or adding durable health storage, stop; this packet is an in-process projection/transport repair only.

## Recovery
Read/projection behavior plus tests only; existing dismissal JSON remains untouched.
