---
type: adr
title: "Keep Inbox JSONL For Capture"
status: accepted
owner: jacob
primary_purpose: Keep the capture inbox as JSONL rather than migrating it to SQLite
derives_from:
  - docs/CONSTITUTION.md
review_cycle: as needed (superseded by replacement ADR)
---

# ADR-0005: Keep Inbox JSONL For Capture

**Status:** Accepted
**Date:** 2026-07-02

## Context

Capture (Quick Capture from iOS, Raycast, Siri) is the highest-value
in-the-moment action Kitty offers. The capture path must keep working
even when richer app state (SQLite, the gateway, the LLM proxy) is
down. A SQLite-only capture path would fail closed in the cases that
matter most.

## Decision

`data/inbox.jsonl` remains append-only and mobile-compatible. It is
allowed to coexist with SQLite because capture must work even when
richer app state is broken.

## Consequences

- Capture writes are durable as long as the filesystem is reachable.
- The JSONL format is the contract; downstream code reads and
  promotes inbox entries into richer stores.
- Adding richer structure to the inbox (e.g. per-line types) is
  allowed; changing the line shape is a breaking change for the
  promotion pipeline.
