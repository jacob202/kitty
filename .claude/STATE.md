# Session State — 2026-07-10 (KPA-01 runtime truth in progress)

## Current branch and inspected commit

- Branch: `feat/kittybuilder-initiative`
- Inspected commit: `0f05ae09ad6a6f90cda4e3bf116278466f72536b`
- Existing untracked files were not touched: `kittybuildercoder.txt` and
  `scripts/run_kittybuilder_free_campaign.sh`.
- Nothing was pushed or committed.

## Completed this session

- Wrote the definitive product architecture and execution plan at
  `docs/KITTY_PRODUCT_ARCHITECTURE.md`.
- Structural review confirmed all 17 requested sections, the adversarial review,
  the go decision, and the first implementation packet are present.
- Implemented KPA-01 additively: `gateway/runtime_manifest.py`,
  `gateway/routes/runtime.py`, route registration, completion binding/metadata,
  trace revision fields, and the Chat runtime status/query surface.
- Python syntax compilation passed for all touched Python modules.
- Runtime smoke check passed and correctly returned explicit `unknown` facts for
  offline LiteLLM, missing project/version, and `available` Builder state.
- Per the user's instruction, no tests, frontend build, browser run, commit, or
  push was performed.

## Important architectural decisions

1. Kitty consolidates around four shared spines: runtime truth, durable product
   state, artifacts/evidence, and governed execution.
2. Chat, Home, Brief, Work/Builder, Image Lab, Memory, Projects, and
   Notifications become views and workflows over those spines rather than
   independent products.
3. The FastAPI gateway remains the product owner and clients remain thin.
4. SQLite is authoritative for app-owned state; Chroma, mem0, caches, and prompt
   context remain derived.
5. Project scope is explicit and persisted. Legacy unscoped data migrates into
   a default Personal workspace/project rather than failing.
6. Runtime facts carry source, evidence, observation time, expiry, and an
   explicit `available | unavailable | degraded | stale | unknown` state.
7. Kitty may claim success only from a succeeded execution receipt containing
   the evidence required for that action kind.
8. Existing Builder queues, runs, leases, recovery, reviews, and initiatives are
   bridged into product state; they are not rewritten.
9. Delivery is incremental and journey-based. No distributed event bus,
   workflow framework, new cloud service, or universal mega-table is proposed.

## Assumptions

- The accepted “gateway is the product” and `memory_graph` read-path ADRs remain
  binding.
- The current Builder initiative/runner work is a valid execution foundation and
  will land through its existing integration process.
- Additive SQLite migrations and local filesystem artifact storage remain the
  preferred implementation path.
- The product continues to optimize for one local user and one machine before
  multi-user or distributed execution.
- Ordinary UI should use product language; raw provider, routing, lease, packet,
  and manifest details remain available in advanced diagnostics.

## Unresolved questions

- Exact TTLs and probe budgets for each runtime capability owner.
- Whether `Workspace` should ship as a persisted entity in the first migration
  or initially be represented by the default Personal project.
- Which existing image, log, report, and generated-file directories are
  canonical enough to register during artifact backfill.
- The precise product boundary between Work and the advanced Builder diagnostic
  view.
- Which provider can supply authoritative cost versus estimated cost, and how
  long local pricing metadata remains valid.

None of these blocks the first packet; each should be settled by its owning
phase before schema or UI commitment.

## Recommended first implementation packet

**KPA-01 — Runtime Truth v1 + Honest Chat Identity**

- Define `CapabilityManifest` v1 with owner and freshness rules.
- Compose app/build, time/timezone, project/repository, Builder summary,
  providers/models, tools, connections, health, and approval limits.
- Expose a snapshot API and compact prompt projection.
- Bind chat attempts to the manifest revision and distinguish requested from
  resolved model/location.
- Replace static Chat model and connection identity with live, user-readable
  truth.

KPA-01 must stay read-oriented and additive. It explicitly excludes chat
normalization, artifact migration, settings redesign, and Builder automation.

## KPA-01 implementation notes

- `/runtime/manifest` is revisioned and expires facts after 15 seconds.
- Chat injects a compact manifest projection and returns the revision in
  non-stream responses and stream headers; trace rows record the revision and,
  for non-stream responses, the resolved model.
- The legacy `/api/models` fallback remains for compatibility, but the new Chat
  runtime badge marks model truth non-live when the authoritative manifest probe
  is unavailable.
- Active project selection is not yet persisted in Chat; absent `project_id` is
  reported as `unknown`, never inferred.

## Prior Builder lane retained

KB-S1A remains complete on this branch. The next Builder-only packet was KB-S1B
(`eligible_packets`, `next_packet`, initiative rollup, blocked-forever detection,
and `initiative status`). Product implementation should decide whether to land
KB-S1B first or keep it isolated while KPA-01 starts; do not mix both into one
review unit.

## Blockers / next actions

- Frontend TypeScript project check passed with
  `tsc -p gateway/kitty-chat/tsconfig.json --noEmit`.
- Review the diff and typecheck the frontend if permitted, then make focused
  corrections or commit KPA-01 as one unit.
- Keep KB-S1B, chat normalization, artifacts, and Builder automation out of this
  packet.
