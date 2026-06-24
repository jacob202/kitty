# Decisions

**Date:** 2026-06-24
**Status:** Canonical forward-looking decision log. Historical detail remains in `docs/DECISIONS_AND_ROADMAP.md`.

## D1 - Local-First Single User

Kitty runs on Jacob's Mac for one user. No multi-tenant cloud architecture in the current roadmap.

## D2 - Gateway Is The Product

All clients stay thin. Product logic belongs in the FastAPI gateway, not Raycast, Telegram, Siri, or the Next.js UI.

## D3 - memory_graph Owns Context Reads

New prompt/search context reads go through `gateway/memory_graph.py`. Phase B may add a write-side router, but should not bypass this read rule.

## D4 - Keep Inbox JSONL For Capture

`data/inbox.jsonl` remains append-only and mobile-compatible. It is allowed to coexist with SQLite because capture must work even when richer app state is broken.

## D5 - Phase B Is Consolidation

Phase B is one storage story and one operating story. No mobile app, cloud sync, push notifications, full agent dashboard, TELOS expansion, or new memory substrate.

## D6 - Borrow Patterns, Not Random Complexity

Code sniping is encouraged when it maps to Kitty's current loop. Borrow proven UX and architecture patterns; do not import a repo's worldview wholesale.

## D7 - StorageRouter Is A Thin Write-Side Seam, Not A Port

`gateway/storage_router.py` (Phase B B4) is a deliberately thin write-side
seam that mirrors the read rule in D3. Routes cross it for mutations; the
underlying store modules do the actual work. The router does **not** try to
abstract the storage substrate, define a generic adapter registry, or hide
the backend.

Why: every prior attempt to build a backend-agnostic port (per-store
adapters, query language, hidden fallback) expanded the seam's surface
without earning anything back. A thin wrapper buys us "every write goes
through one module" at zero abstraction cost. The substrate can change
later if a real migration needs it; the seam does not pre-pay for that.

What this rules out:
- New methods on `storage_router` for stores that don't currently have a
  write seam (e.g. `desktop_store`, `token_usage_log`, `model_digest`).
- Generic `append`/`upsert`/`read` verbs that hide which backend is used.
- "Smart" router code that retries, caches, or falls back across backends.

What this allows:
- Wrapping any new write site in a one-line function that delegates to
  the underlying store, as B4 did for todos and plugin settings.
- Replacing the thin wrapper with a real port later if a migration needs
  it (the migration would be local; consumers would only change at the
  call site).

The chats migration (Phase C C0–C6) and the journal migration (Phase C
B0–B6) followed the same pattern but did **not** go through
`storage_router` — those are new read/write modules of their own. The
router is for legacy stores that already have a write API in
`todo_store` / `plugin_registry`; new modules get their own.

### D7 Amendment (2026-06-24) — Registration Is Allowed; Behavior Is Not

The Gateway Architecture Deepening Program
(`docs/superpowers/specs/2026-06-24-gateway-deepening-program-design.md`,
Phase 1) requires `storage_router.py` to become the canonical import
point for store modules. This amendment keeps D7's "thin seam, not a
port" framing and clarifies what the deepening program may add without
turning the router into a port.

Still ruled out:

- Generic `append` / `upsert` / `read` / `delete` verbs that hide the
  backend. Routes call typed methods on the router, not string-keyed
  dispatch.
- "Smart" router code that retries, caches, or falls back across
  backends. The router forwards; it does not decide.
- A `dict` / `getattr` adapter table exposed to routes. Even if the
  router holds a reference to every store, routes get typed accessors
  (`router.journal` → `journal_store`), not a registry they can index
  into.

Now allowed:

- A registration step in `storage_router.py` that each store module
  calls at import time (e.g. `register(store_module)`). The router
  holds the reference; routes consume typed accessors. The router is
  the single import point, not a dispatcher.
- Cross-cutting concerns that do not introduce port behavior:
  - **Validation** at the router boundary — typed entry points reject
    bad shapes before they reach a store.
  - **Migration triggers** — when a store's underlying schema changes,
    the router runs the migration before forwarding.
  - **Telemetry** — every write logs to `data/storage_writes.jsonl`
    with `{ts, store, op, key, ms}`, read by `/status/glance` for
    observability.

**Litmus test:** if the router would need to know about a *new backend*
to handle a new store, it is a port. If the router just holds a
reference and exposes a typed method, it is a seam. The amendment
keeps it a seam.
