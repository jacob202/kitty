---
type: roadmap
title: "Kitty Roadmap"
status: canonical
owner: jacob
primary_purpose: Strategic direction and phased implementation plan
derives_from:
  - docs/VISION.md
  - docs/CONSTITUTION.md
implements:
  - docs/VISION.md
referenced_by: []
review_cycle: monthly
---

# Kitty Roadmap

Strategic direction derived from the Vision and Constitution. Implementation phases are ordered by dependency and user value.

## Current Phase

**Phase: Governance Foundation** (this initiative)

Establishing the documentation architecture that every future subsystem derives from.

## Product Spine

The product architecture (`docs/product/KITTY_PRODUCT_ARCHITECTURE.md`) defines four shared spines:

1. **Runtime truth** — authoritative facts about Kitty, context, capabilities, health.
2. **Durable product state** — explicit relationships among projects, conversations, work, decisions.
3. **Artifacts and evidence** — one lifecycle for every durable input and output.
4. **Governed execution** — one initiative and approval policy across tools, Builder, and background jobs.

## Implementation Phases

### Phase 0 — Contract Freeze and Migration Inventory

Define versioned schemas. Assign source owners. Inventory legacy data. No user-visible change.

### Phase 1 — Runtime Truth Plus Honest Identity

Implement the capability manifest, owner probes, freshness semantics. Replace hardcoded model/connection identity in Chat with live truth.

### Phase 2 — Durable Chat Plus Attachments

Normalized conversations, turns, messages, attempts. Persist before dispatch. Attachment artifacts and ingestion receipts.

### Phase 3 — Artifact/Evidence Spine Plus Image Lab

Artifact registry, local storage boundary, provenance, previews. Execution receipts for image generation and core tool actions.

### Phase 4 — Product State Plus Home/Brief/Notifications

Activity events and cross-domain relationships. Now, Changed, Needs attention, Resume, and Brief projections.

### Phase 5 — Governed Builder as Work

Bridge product work/run IDs to Builder initiatives. Complete self-building contracts, validation/review, bounded repair, budgets.

### Phase 6 — Consolidation and Retirement

Move remaining consumers to shared contracts. Remove obsolete truth paths. Align docs to shipped architecture.

## Life-First Ordering

Per ADR-0016, life projects (job search, benefits, education, health, money) always outrank code projects — including Kitty itself — in "What's Next" rankings.
