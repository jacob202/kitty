# Work Projection Vertical Slice — Design

**Date:** 2026-08-13  
**Owner:** campaign lead / interactive implementation  
**Base:** `origin/main` `1172f98e49b46d0d13c69fbf0832875c8255777b`

## Outcome
Kitty exposes one product-shaped, read-only Work projection from Gateway that turns existing Builder durable truth into user language without creating a new queue, store, scheduler, approval system, or execution state machine.

## Authority
- Gateway owns the Work API and product vocabulary.
- Builder remains the sole owner of initiatives, packets, tasks, runs, retries, reviews, budgets, publication, and execution evidence.
- Gateway reads Builder only through `gateway.builder_status.build_status_snapshot()`.
- Discord and Console later consume this same Work API; neither joins Builder storage.
- Gateway approval is separate. No durable Builder↔Gateway approval identity link exists today, so this slice reports approval as `unavailable` with an exact reason rather than guessing.

## API
Add `GET /work` returning schema version 1, observation/freshness metadata, source health, aggregate counts, and a bounded list of Work items. One Work item maps to one Builder initiative and carries its authoritative Builder identity.

Each item exposes: `work_id`, `title`, `state`, `current_packet`, `blocker`, `approval`, `evidence`, `next_action`, `updated_at`, and `source`. `current_packet` is selected deterministically from the initiative's own next eligible packet, otherwise the first non-terminal packet, otherwise the most recently updated packet.

Product state is derived only from explicit Builder facts: running run → `active`; paused initiative → `paused`; failed initiative/packet → `failed`; blocked packet/eligibility → `blocked`; completed initiative → `completed`; eligible/queued work → `ready`; otherwise `waiting`.
## Evidence and honesty
`evidence` summarizes only persisted attempt validation/review/publication facts already present in the Builder snapshot. Missing validation, review, artifacts, logs, or approval links remain explicitly unavailable; they are never converted into success.

The response includes `observed_at` and `valid_until`. A direct successful snapshot is `available` unless Builder reports partial integrity, which becomes `degraded` with a reason. A snapshot read failure is an HTTP 503 with its concrete reason; the route does not return an empty successful payload.

## First-slice non-goals
- No Builder mutation or new initiative.
- No pause/resume UI yet.
- No chat-to-Work proposal path yet.
- No Discord Phase 1 change yet.
- No image work in this packet.
- No runtime service switch/restart.

## Follow-on sequence
1. Console `WorkView` consumes `GET /work` and renders loading, empty, degraded/stale, blocker, approval-unavailable, evidence, and detail states.
2. Run the changed Gateway/Console from this exact worktree on isolated ports for runtime/browser proof; production split-checkout remains a separate blocker until explicitly switched.
3. Discord Phase 1 consumes `GET /work` for the Master Control Thread and links one thread to one authoritative Work identity.
4. Only after that proof, add bounded Gateway command endpoints for approved pause/resume/proposal steering.

## Rejection conditions
Reject this design if any implementation queries Builder SQLite directly outside the supported projection, stores Work state durably, invents approval linkage, treats `awaiting_review` as Jacob approval, or claims runtime acceptance from source/tests alone.