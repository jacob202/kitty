# Handoff — 2026-07-10 (KPA-02b artifacts complete)

## Branch

`feat/kittybuilder-initiative`

## Completed in this session

- Added `gateway/runtime_manifest.py`: versioned, revisioned runtime manifest
  with explicit fact states, source, observation time, expiry, and reasons.
- Added `GET /runtime/manifest` through `gateway/routes/runtime.py` and route
  registration.
- Bound chat completions to a manifest revision and injected compact runtime
  truth into the system context.
- Added runtime revision/model metadata to completion responses, stream headers,
  and gateway trace records.
- Added the Chat runtime status badge and runtime-manifest query; authoritative
  model IDs are used when the manifest probe succeeds and are marked non-live
  when it does not.
- Updated the architecture and state documents from the planning handoff.
- Committed locally as `25b7f3f` (`feat(runtime): add authoritative manifest to chat`).
- Added `gateway/project_context.py` using the existing SQLite `app_settings`
  seam; added `GET/PUT /context/project`.
- The manifest now resolves omitted project scope from the persisted active
  project, defaulting once to the first active project.
- Chat now sends the active `project_id`, and the TopBar exposes a project
  selector that invalidates runtime truth after switching.
- Committed locally as `e95275b` (`feat(context): persist active project scope`).
- Added migration `016_chat_lifecycle.sql` and `gateway/chat_lifecycle.py` for
  normalized conversations, turns, attempts, and messages beside the legacy
  chat blob.
- Identified Chat requests now persist the user message and running attempt
  before provider dispatch; success, failure, and stream interruption finalize
  durable lifecycle state.
- Chat sends conversation/title/message IDs and receives turn/attempt headers.
- Committed locally as `d091352` (`feat(chat): persist normalized turn lifecycle`).
- Added migration `017_artifacts.sql` and `gateway/artifact_store.py` for
  durable file metadata, hashes, provenance, and ingestion status.
- `/capture/file` now registers an attachment artifact after the atomic write;
  background ingestion updates its explicit processing status.
- Added read-only `/artifacts` and `/artifacts/{id}` endpoints plus
  `/chats/{id}/lifecycle` normalized turn reads.
- Committed locally as `80759cd` (`feat(artifacts): register captured files durably`).

## Verification performed

- `python3.12 -m py_compile` passed for all touched Python modules.
- Runtime composer smoke check passed. With LiteLLM offline, it emitted explicit
  warnings and returned `unknown` for LiteLLM/model/project/version facts;
  Builder state returned `available`.
- No tests, frontend build, or browser run was performed. Nothing was pushed.

## In-flight / review notes

- Frontend TypeScript project check passed with `tsc -p gateway/kitty-chat/tsconfig.json --noEmit`.
- `/api/models` still has its legacy fallback for compatibility. Chat's new
  runtime badge no longer treats that fallback as live, but a later packet
  should retire the endpoint fallback once all consumers use the manifest.
- Active project selection is now persisted through `/context/project`; an
  explicit request `project_id` still overrides the persisted scope.
- Attachments, normalized chat reads, offline outbox replay, and UI recovery
  from the lifecycle ledger remain intentionally out of this packet. Capture
  registration is ready, but the Chat composer does not yet upload files.
- The untracked files `kittybuildercoder.txt`,
  `scripts/run_kittybuilder_free_campaign.sh`, and the oddly named existing
  untracked file beginning `-iname` were not touched.

## Next action

KPA-01, KPA-01b, KPA-02a, and KPA-02b are committed locally. The next focused
packet is Chat composer attachment upload/linking; do not mix KB-S1B, Builder
automation, or the full offline outbox into that packet.
