---
type: adr
title: "Local-First Single User"
status: accepted
owner: jacob
primary_purpose: Commit to local-first single-user architecture as a permanent design constraint
derives_from:
  - docs/CONSTITUTION.md
review_cycle: as needed (superseded by replacement ADR)
---

# ADR-0002: Local-First Single User

**Status:** Accepted
**Date:** 2026-07-02

## Context

Kitty could be designed as a multi-tenant cloud SaaS, a local-first
personal tool, or something in between. The cloud path costs money per
user, requires auth, infra, ops, and ongoing security review. The
local-first path trades scale for simplicity and control.

## Decision

Kitty runs on Jacob's Mac for one user. No multi-tenant cloud
architecture in the current roadmap.

## Consequences

- No cloud infra to run, no auth to harden, no per-user billing.
- All "sharing" with Kitty is a remote-access question (Tailscale),
  not a multi-user question.
- Future expansion to other users is not foreclosed but is not on the
  roadmap; if it happens, the storage and LLM-call layers will need
  real per-tenant boundaries.
