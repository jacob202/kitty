# KF-SEARCH-01 — Search returns every default store it actually searched

**Initiative:** `kitty-opens-the-doors-20260831-v2`
**Owner:** builder
**Free or paid:** free
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Backend-only packet. Its visible UI/actionability is owned by a manifest-less interactive companion.

## What Jacob can do after this
The bounded capability in this packet is implemented and proven without creating a parallel system.

## Why this is the next thing
MemoryGraph default keys are nine; the search normalizer/route map only five, dropping projects, explicit_memory, traces and signals.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
gateway/memory_graph.py default MemoryGraph fans out to nine canonical stores: projects, explicit_memory, memory, knowledge, journal, traces, todos, inbox and signals. gateway/search.py RAW_TO_SECTION maps only memory/knowledge/journal/todos/inbox, and gateway/routes/search.py flattens only those same five sections, so hits from projects, explicit_memory, traces and signals are silently dropped even though the response reports those stores were searched. Normalize all nine default stores without changing memory_graph: merge explicit_memory hits into the visible memories section while preserving each hit's source/provenance, and add stable project, trace and signal sections/kinds that the HTTP route also returns. Preserve the global result limit and round-robin balancing across stores, failure isolation, degraded_stores, errors and provenance. Remove the dead RAW_TO_SECTION alias only if tests prove no producer emits it. This packet creates no new files.

## Acceptance criteria
- A hit from explicit_memory appears in search results as a memory while retaining source explicit_memory and its metadata/provenance.
- Hits from projects, traces and signals are returned rather than silently discarded.
- The HTTP /search response can surface all nine default MemoryGraph stores while preserving its global limit and round-robin balancing.
- A degraded or failed store still cannot suppress healthy results from other stores, and errors/degraded_stores remain truthful.
- Existing memory, knowledge, journal, todo and inbox hit shapes remain compatible.
- gateway/memory_graph.py is unchanged.
- python -m pytest -q tests/test_search.py tests/test_memory_graph.py passes.

## Verification
**Tier 1 — mechanical.** Builder-runnable commands:
  - `python -m pytest -q tests/test_search.py tests/test_memory_graph.py`
  - `python -m ruff check gateway/search.py gateway/routes/search.py tests/test_search.py tests/test_memory_graph.py`

**Tier 2 — running app.** Not applicable to this backend-only half; its manifest-less interactive companion owns the running-app Playwright smoke.

**Tier 3 — product acceptance.** Not applicable to this backend-only half; independent Product Acceptance is required on the user-facing companion before the door is considered finished.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
If exposing a store requires changing its storage adapter or adding a new search backend, stop; this packet is normalization/transport only.

## Recovery
Read path only; no migrations or external effects.
