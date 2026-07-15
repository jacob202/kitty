---
type: adr
title: "Gateway Is The Product"
status: accepted
owner: jacob
primary_purpose: Establish that the FastAPI gateway owns all product logic; clients are thin views
derives_from:
  - docs/CONSTITUTION.md
review_cycle: as needed (superseded by replacement ADR)
---

# ADR-0003: Gateway Is The Product

**Status:** Accepted
**Date:** 2026-07-02

## Context

Kitty has many clients: the Next.js UI, Raycast, Telegram, Siri, an
iMessage bridge, and potentially more. Product logic could live in
each client, or in one place. The "one place" alternative is the
FastAPI gateway (`gateway/`).

## Decision

All clients stay thin. Product logic belongs in the FastAPI gateway,
not Raycast, Telegram, Siri, or the Next.js UI.

## Consequences

- Each client is a thin view over gateway APIs.
- New product features land in `gateway/` and become available to
  every client automatically.
- A client that needs offline behavior (e.g. iMessage draft on the
  phone) must explicitly carve out the offline path; it cannot be
  the default.
