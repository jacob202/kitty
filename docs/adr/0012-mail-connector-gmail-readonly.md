---
type: adr
title: "Mail Connector Uses The Gmail API, Read-Only"
status: accepted
owner: jacob
primary_purpose: The mail connector is read-only Gmail API, never IMAP or send
derives_from:
  - docs/CONSTITUTION.md
review_cycle: as needed (superseded by replacement ADR)
---

# ADR-0012: Mail Connector Uses The Gmail API, Read-Only

**Status:** Accepted
**Date:** 2026-07-02 (decided by Jacob; §16.2 in `docs/OPERATOR_STRATEGY.md`)

## Context

The mail connector (packet 005) needs a read path. Two candidates:
Gmail API (Google OAuth, cloud-side data fetch) or Apple Mail via
AppleScript (Mac-only, brittle). The Gmail path is robust and
scriptable; the AppleScript path is brittle and Mac-only.

## Decision

The mail connector uses the **Gmail API, read-only scope** — not
Apple Mail via AppleScript.

**Why Gmail over AppleScript:** robust and scriptable vs brittle
and Mac-only. The tradeoff accepted: Google OAuth and a cloud API
sit in the read path.

## Consequences

What this commits to:

- Read-only scope (`gmail.readonly`). Sending stays off the table
  until the action queue has earned trust (per §16.2 — draft-only
  regardless of transport).
- Mail **bodies are `mail_body` class = local-only** under
  ADR-0011. The Gmail API fetches them, but they must not be
  routed to cloud LLMs. Fetching via Google was accepted;
  processing stays local.
- Connector shape follows §17.2: cron-polled adapter emitting
  deduped signal rows. No webhooks, no push.

What this rules out:

- AppleScript/Apple Mail integration for mail.
- Any write scope in v1 (send, label, archive, delete).
