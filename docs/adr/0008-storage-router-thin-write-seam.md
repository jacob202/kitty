# ADR-0008: StorageRouter Is A Thin Write-Side Seam, Not A Port

**Status:** Accepted
**Date:** 2026-07-02

## Context

`gateway/storage_router.py` (Phase B B4) is a write-side seam that
mirrors the read rule in ADR-0004. The temptation when adding a
router is to make it a real port: backend-agnostic verbs, fallback
logic, an adapter registry. Every prior attempt at that has
expanded the seam's surface without earning anything back.

## Decision

The router is a deliberately thin wrapper. Routes cross it for
mutations; the underlying store modules do the actual work. It does
**not** try to abstract the storage substrate, define a generic
adapter registry, or hide the backend.

Why: a thin wrapper buys "every write goes through one module" at
zero abstraction cost. The substrate can change later if a real
migration needs it; the seam does not pre-pay for that.

## Consequences

What this rules out:

- New methods on `storage_router` for stores that don't currently
  have a write seam (e.g. `desktop_store`, `token_usage_log`,
  `model_digest`).
- Generic `append`/`upsert`/`read` verbs that hide which backend is
  used.
- "Smart" router code that retries, caches, or falls back across
  backends.

What this allows:

- Wrapping any new write site in a one-line function that
  delegates to the underlying store, as B4 did for todos and plugin
  settings.
- Replacing the thin wrapper with a real port later if a migration
  needs it (the migration would be local; consumers would only
  change at the call site).

The chats migration (Phase C C0–C6) and the journal migration
(Phase C B0–B6) followed the same pattern but did **not** go
through `storage_router` — those are new read/write modules of
their own. The router is for legacy stores that already have a
write API in `todo_store` / `plugin_registry`; new modules get
their own.
