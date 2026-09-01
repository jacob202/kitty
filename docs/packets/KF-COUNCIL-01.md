# KF-COUNCIL-01 — A normal chat turn can use Council and still returns one answer

**Initiative:** `kitty-opens-the-doors-20260831-v4`
**Owner:** builder (held)
**Builder manifest:** held
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Backend packet intentionally held out of Builder. Hold reason: Making Council a normal chat door requires the chat-completions integration seam, and active PR #732 currently owns gateway/routes/completions.py. The standalone /council route already works; duplicating a second chat transport would violate the product architecture.

## What Jacob can do after this
The bounded capability in this packet is implemented and proven without creating a parallel system.

## Why this is the next thing
Council itself and /council are tested, and the frontend already defines Council routing metadata, but normal /api/chat/completions never calls Council. PR #732 currently owns the required completions seam.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
gateway/council.py and POST /council already classify, dispatch, verify and synthesize one coherent answer, and the frontend Message type already has routing metadata shaped for Council. The missing door is the normal chat transport: no chat path invokes Council, so a user cannot reach it from the operating layer. Integrate Council through the existing chat-completions lifecycle rather than adding a second frontend chat state machine or a new queue. The final user-visible assistant turn remains one synthesized answer; specialist routing is metadata/evidence, not multiple competing replies. Preserve normal chat persistence, failure truth and explicit model override behavior. Do not change Council's specialist algorithms unless the integration proves a concrete incompatibility. This packet creates no new files.

## Acceptance criteria
- An eligible normal chat request can invoke the existing Council supervisor without the frontend calling POST /council as a separate conversation transport.
- The chat response contains one synthesized assistant answer and bounded Council routing metadata, never raw specialist fragments as separate assistant messages.
- Council failure remains truthful: unusable specialist output is identified as failed and is not silently presented as a successful contribution.
- Normal non-Council chat and explicit model overrides preserve their current routing behavior.
- The existing chat lifecycle still records the user turn and final assistant answer through its canonical persistence path.
- python -m pytest -q tests/test_council.py tests/test_council_route.py tests/test_chat_completions.py passes.

## Verification
**Tier 1 — mechanical.** Not run while held. After the hold clears, run:
  - `python -m pytest -q tests/test_council.py tests/test_council_route.py tests/test_chat_completions.py`
  - `python -m ruff check gateway/council.py gateway/routes/completions.py tests/test_council.py tests/test_council_route.py tests/test_chat_completions.py`

**Tier 2 — running app.** Not applicable until the hold clears; the eventual interactive companion owns browser smoke proof.

**Tier 3 — product acceptance.** Not applicable until the hold clears and the user-facing companion is ready for independent Product Acceptance.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
Do not implement while an active PR owns gateway/routes/completions.py; after release, stop if integration would require a parallel frontend conversation transport or bypass canonical chat lifecycle persistence.

## Recovery
Chat routing/persistence integration and tests only. No new store, queue, provider credential, or irreversible side effect.
