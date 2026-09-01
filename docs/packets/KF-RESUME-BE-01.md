# KF-RESUME-BE-01 — A chat reply keeps producing durable output after the browser connection disappears

**Initiative:** `kitty-opens-the-doors-20260831-v7`
**Owner:** builder (held)
**Builder manifest:** held
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Backend packet intentionally held out of Builder. Hold reason: PR #732 owns gateway/routes/completions.py. Compile the prerequisite now but do not queue it until that PR lands and the base/path fence is refreshed.

## What Jacob can do after this
Kitty can finish and retain a reply even if Jacob reloads or closes the browser connection mid-generation.

## Why this is the next thing
The durable lifecycle ledger and turn headers exist, but assistant text is only written on finish_turn; a browser disconnect can terminate the response generator before there is a durable answer to recover.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
Create the backend prerequisite for KF-RESUME-01. The chat lifecycle already assigns durable turn/attempt ids and /api/chat/completions returns X-Kitty-Turn-ID/X-Kitty-Attempt-ID, while GET /chats/{id}/lifecycle can read the ledger; however assistant content is committed only when finish_turn runs at the end of the response stream. Refactor the streaming execution boundary so the provider producer is owned by a durable server-side turn task/buffer rather than the lifetime of one HTTP client connection. Persist bounded assistant progress/final output through the canonical chat lifecycle and make lifecycle reads expose enough status/content for a new client to reattach. A disconnected browser must not cancel a still-valid provider generation solely because its SSE consumer vanished. Preserve explicit cancellation semantics and fail closed on gateway restart/interrupted provider work. Do not create a second chat store or an unbounded in-memory transcript.

## Acceptance criteria
- A streaming turn has a durable turn id before content delivery and its producer is not cancelled solely by HTTP client disconnect.
- Assistant progress/final output is bounded and recoverable through the canonical chat lifecycle authority.
- GET /chats/{id}/lifecycle exposes enough turn status/content for a new client to determine running, completed, failed or interrupted truth.
- Explicit user cancellation still stops generation and records a terminal state.
- Gateway restart reconciles genuinely interrupted producer work instead of claiming it is still running.
- Normal connected SSE clients still receive ordered chunks and one terminal completion/error.

## Verification
**Tier 1 — mechanical.** Not run while held. After the hold clears, run:
  - `python -m pytest -q tests/test_chat_lifecycle.py tests/test_chat_completions.py tests/test_chats_routes.py`
  - `python -m ruff check gateway/chat_lifecycle.py gateway/routes/completions.py gateway/routes/chats.py tests/test_chat_lifecycle.py tests/test_chat_completions.py tests/test_chats_routes.py`

**Tier 2 — running app.** Not applicable until the hold clears; the eventual interactive companion owns browser smoke proof.

**Tier 3 — product acceptance.** Not applicable until the hold clears and the user-facing companion is ready for independent Product Acceptance.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
Do not implement while PR #732 owns gateway/routes/completions.py. After it lands, stop again if preserving the answer requires browser-local buffering, an unbounded in-memory task, or bypassing the canonical chat lifecycle ledger.

## Recovery
Durable chat lifecycle/transport changes and tests only. No new provider credential or second conversation store; interrupted work must remain inspectable and retryable.
