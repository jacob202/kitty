# KF-COPY-01 — Builder events expose stable title keys instead of forcing the UI to translate raw event types

**Initiative:** `kitty-opens-the-doors-20260831-v5`
**Owner:** builder
**Free or paid:** free
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Backend-only packet. Its visible UI/actionability is owned by a manifest-less interactive companion.

## What Jacob can do after this
The bounded capability in this packet is implemented and proven without creating a parallel system.

## Why this is the next thing
Builder's durable status projection exposes raw last_event.type and reason only; the frontend currently manufactures labels from those implementation strings, which is exactly the copy ownership drift UX_RULES rule 4 forbids.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
gateway/builder_status.py _event_projection() currently returns raw event type, reason and retry-budget truth. BuilderSurface then calls displayState(packet.last_event.type) and concatenates the raw reason, which makes the client infer product copy from implementation strings. Add a bounded server-owned event-copy contract to the existing last_event projection: a stable title_key plus event-specific placeholders derived only from already-loaded event payload/status facts. Cap every placeholder string at 80 characters as required by docs/UX_RULES.md rule 4. Preserve type, reason and counts_toward_budget unchanged for backward compatibility and technical disclosure. Known decision-bearing event classes such as scope violation, identity verification failure, infrastructure failure/interruption and retry exhaustion must receive explicit semantic keys; unknown events must degrade to one neutral bounded key rather than leaking an arbitrary implementation string as the primary title. Do not render final English sentences on the server, change Builder state transitions, alter event storage, or touch frontend files. This packet creates no new files.

## Acceptance criteria
- Projected Builder last_event includes title_key and placeholders in addition to the existing type, reason, created_at and counts_toward_budget fields.
- Known user-relevant failure/decision event classes map to stable semantic title keys rather than requiring a client to humanize the raw event type.
- Every string placeholder value is truncated to at most 80 characters while the existing raw bounded reason remains available separately for technical disclosure.
- An unknown event type receives a neutral stable title_key and bounded placeholder data; it is not promoted verbatim into a user-facing sentence by the backend contract.
- Existing Builder status state, failure_kind derivation, retry-budget truth and event reason sanitization remain unchanged.
- No event row or Builder durable state is rewritten by projection.
- python -m pytest -q tests/test_builder_status.py passes.

## Verification
**Tier 1 — mechanical.** Builder-runnable commands:
  - `python -m pytest -q tests/test_builder_status.py`
  - `python -m ruff check gateway/builder_status.py tests/test_builder_status.py`

**Tier 2 — running app.** Not applicable to this backend-only half; its manifest-less interactive companion owns the running-app Playwright smoke.

**Tier 3 — product acceptance.** Not applicable to this backend-only half; independent Product Acceptance is required on the user-facing companion before the door is considered finished.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
If satisfying the copy contract would require changing event storage/schema or frontend rendering, stop. This packet only adds backward-compatible projection metadata from facts already present in the status read.

## Recovery
Pure read projection plus tests; no migration, queue transition, event rewrite, provider call, or product-data mutation.
