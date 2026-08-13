# Gateway Work Spine v1 — Design

## Goal

Create one Gateway-owned read model for active and completed work so Discord and the Kitty Console can show the same truth without creating a second task system.

V1 proves this against KittyBuilder first. It does not replace Builder state, duplicate execution records, or add new write/approval semantics.

## Chosen approach

Expose a small Gateway projection over the existing KittyBuilder durable store. Builder remains authoritative for engineering execution; Gateway translates Builder records into a stable consumer-facing Work shape.

Rejected for v1:
- Extending Discord first: would force Discord to interpret Builder state itself.
- Building Console Work first: would duplicate the same interpretation in UI code.
- Creating a new Work database: would introduce synchronization and ownership ambiguity.

## Source of truth

Use existing Builder records only:
- `tasks` for identity, state, blockers, scope and final report.
- append-only `events` for chronology.
- `runs` for execution/model evidence.
- `pr_links` for publication/review/merge evidence.

The Work Spine owns projection logic, not those records. V1 performs no Builder DB writes.

## Consumer API

### GET /work
Returns newest/relevant Work items with bounded pagination/filtering. V1 supports state, source, and limit; default source is all supported sources (Builder only in v1).

### GET /work/{work_id}
Returns one Work item with its current projection, latest run, latest PR, blocker/error, and completion evidence. Unknown IDs return 404.

### GET /work/{work_id}/events
Returns normalized chronological events derived from Builder append-only event stream. It never synthesizes success when source evidence is missing.

All routes use existing Gateway authentication/route conventions. Source read failure is a visible 503-style error, not an empty successful result.

## Stable Work identity

V1 Work IDs are namespaced: builder:<builder_task_id>.

Each item also carries source=builder and source_id=<builder_task_id>. The namespace makes later image/chat/project adapters possible without collisions or migrations.

## Work state model

Expose both normalized state and exact source_state. Normalize Builder states as follows:
- queued, claimed -> pending
- running -> running
- blocked -> blocked
- awaiting_review, pr_opened -> review
- done -> completed
- failed -> failed
- cancelled -> cancelled

Unknown future Builder states fail visibly in projection tests rather than silently mapping to success.

## Work item shape

Every Work item includes: `work_id`, `source`, `source_id`, `title`, `summary`, `state`, `source_state`, `priority`, `created_at`, `updated_at`, `blocker`, `error`, `latest_run`, `latest_pr`, `evidence`, and `links`.

Evidence is derived, not invented. For completed Builder work, evidence exposes the final report, stored validation/review facts, and merged PR metadata when present.

## Components

1. `gateway/work_spine.py` — pure projection functions from Builder records to Work records. No HTTP concerns and no writes.
2. `gateway/routes/work.py` — read-only FastAPI routes, filtering, validation and HTTP errors.
3. `gateway/routes/register.py` — normal route registration only.
4. `gateway/models/work.py` — typed response models if the existing route pattern benefits from them.

Do not read SQLite directly from the route when an existing Builder facade function exists. Extend the Builder read facade only when necessary for a bounded query such as latest run.

## Data flow

Consumer -> Gateway `/work` -> Work Spine projector -> Builder read APIs -> durable Builder DB.

Discord and Console consume Gateway responses only. They must not open Builder SQLite directly or derive their own state mappings.

V1 is polling/read based. Realtime fan-out can later reuse Builder event broadcasting without changing Work identity or state semantics.

## Error and trust rules

- Unknown Work ID: 404.
- Builder store unavailable/corrupt: fail visibly; do not return an empty successful list.
- Missing optional evidence: return `null`/empty evidence with the source state unchanged.
- Never infer `completed` from a PR alone; Builder task state remains authoritative.
- Never expose credentials, raw environment values, or unrestricted log contents through Work responses.

## V1 acceptance proof

1. The merged KPROOF `/version` Builder task appears through `/work` as `completed` with its Builder source ID, merged PR #484, and available completion evidence.
2. At least one live nonterminal Builder task projects correctly as `pending`, `running`, `blocked`, or `review` without changing Builder state.
3. `/work/{id}/events` preserves Builder event order and source timestamps.
4. Unknown IDs and source failures are explicit errors.
5. Projection tests prove all known Builder state mappings and reject an unknown state.
6. Existing Builder tests remain green and the route has focused API tests.

## Non-goals for v1

- Creating, approving, cancelling or retrying work.
- New durable Work tables.
- Discord message/thread orchestration.
- Console UI changes.
- Image/chat/project adapters.
- WebSocket/SSE transport.
- Changing Builder execution, budgets, review, publication or merge behavior.

## Next slice after v1

Wire Discord Command Center and the Console Work surface to this API. Any future action endpoint must delegate to the owning subsystem rather than mutate Work projection state directly.
