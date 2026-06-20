# Decisions

**Date:** 2026-06-20
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
