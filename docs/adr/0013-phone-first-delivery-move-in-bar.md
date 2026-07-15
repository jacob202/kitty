---
type: adr
title: "Phone-First Delivery And The Move-In Bar"
status: accepted
owner: jacob
primary_purpose: The phone is the primary delivery surface; the "move-in bar" gates what ships
derives_from:
  - docs/CONSTITUTION.md
review_cycle: as needed (superseded by replacement ADR)
---

# ADR-0013: Phone-First Delivery And The Move-In Bar

**Status:** Accepted
**Date:** 2026-07-04 (decided by Jacob in the H1 planning session, packets 015-020)

## Context

Jacob has never used Kitty and won't until it clears a bar he
defined. He is phone-first: always on the iPhone, rarely at a Mac.
The MacBook Air (broken screen, previously offline) becomes Kitty's
headless always-on home once it has an ethernet adapter.

## Decision

**Delivery channel:** iOS push, not the web UI, not Telegram (he
never opens it), not email (buried). First try iMessage-to-self
via the existing `gateway/imessage.py` bridge (free); fall back to
the existing Pushover integration in `gateway/notify.py` (~US$5
one-time) if AppleScript fights back. Packet 015.

**The review contract:** anything needing Jacob's eyes (screenshots,
reports, approvals) is pushed TO him. "Show me, I'm not gonna go
looking for this." No review step may assume he opens an app
unprompted.

**The move-in bar (H1 done-enough):** morning brief on the phone
with real mail and deadlines; one concrete next step per project
("what's B"); benefits/admin paper watched with escalating
deadline alerts (triggered by the June 2026 ~$600
repayment-assistance miss); capture that comes back; everything
auditable in the queue. Defined in `docs/packets/README.md`.

**Priority order among life domains:** projects navigator first
(his pick), then benefits/disability (SAID/CDB/DTC is the income
track), then car and body expert packs. **Job search is parked** —
"plan it, don't build it," packet 019 activates only on his
explicit say-so. The recovery expert pack is built only on his
explicit opt-in, local-only, and Kitty does not raise it.

## Consequences

What this rules out:

- Shipping user-facing features with no push path to the phone.
- Telegram as a delivery assumption anywhere in the product.
- Treating job search or any H2 ambition (voice, mobile-native,
  other users) as in-scope before move-in day.
