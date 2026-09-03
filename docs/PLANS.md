# Kitty Planning Index

**Status:** Navigation and disposition index; not a roadmap
**Updated:** 2026-09-03
**Roadmap authority:** `docs/ROADMAP.md` — the only roadmap
**Mission record:** `docs/ACTIVE_MISSION.md` — current approved mission/acceptance contract; re-read it for present status

`docs/ROADMAP_V2.md` is historical/superseded milestone detail, not an active roadmap. This file exists to point readers
to reviewed plans and to prevent older session plans from silently regaining
authority.

## Operating rule

- Use `docs/ROADMAP.md` for priority and sequencing.
- Use `docs/ACTIVE_MISSION.md` for the canonical mission record and its current status/acceptance contract.
- Treat every file under `docs/plans/` as supporting evidence unless the
  canonical roadmap explicitly activates it. The former `docs/planning/` folder
  was archived to `docs/archive/planning-2026-07-24/` on 2026-09-03.
- A plan that describes an older repository state must be superseded or
  archived rather than left marked “ready to implement.”
- Accepted ADRs own durable architecture decisions even when an older plan
  contains a conflicting model, provider, or mechanism recommendation.

## Reviewed implementation plans

### Image Lab — preserved lifecycle, superseded model/mechanism choices

**Historical reviewed plan:**
`docs/plans/image-studio-character-first-architecture-2026-07-28.md`

The July 28 plan remains useful evidence for the character-first/session-oriented
product goal, dual hosted/private boundary, durable job lifecycle, cost discipline,
consent/safety framing, measurable identity evidence, and bounded repair/retry
principles.

**Current durable execution decision:**
`docs/adr/0040-image-lab-flux2-execution-architecture.md`

ADR 0040 supersedes the July plan's model/provider/mechanism choices where they
conflict. The v1 architecture is FLUX.2-first, with provider-neutral `ImageIntent`,
a versioned semantic compiler, native multi-reference and native editing as the
first mechanism, replaceable transports, and benchmark-gated escalation to LoRA
or other identity/repair machinery only if native capability fails Kitty's
acceptance bar.

This index does not activate Image Lab implementation by itself. Priority and
sequencing remain owned by `docs/ROADMAP.md` plus explicit Jacob approval and the current mission/ownership chain.

Superseded Image Studio evidence:

- `docs/archive/planning-2026-07-24/image-studio-character-system-2026-07-24.md` — older repository state and provider assumptions.
- Other removed session plans remain recoverable from Git history; missing paths are not current planning inputs.

### KittyBuilder

- `docs/plans/KITTYBUILDER_DAILY_DRIVER_PLAN.md` — retained as supporting design
  evidence; sequencing belongs to `docs/ROADMAP.md`.
- `docs/plans/feat-kittybuilder-follow-on-roadmap.md` — retained backlog input,
  not an independent roadmap.

### Product experience and coherence

- `docs/plans/KITTY_PRODUCT_EXPERIENCE_V1.md` — retained supporting design evidence; it is not an authority unless ratified.
- `docs/plans/KX_COHERENCE_AUDIT.md` — retained audit input.
- Removed session-specific plan files remain available through Git history rather than dangling current links.

## Historical status

The previous contents of this file were a 2026-07-24 session tracker. They
claimed an older roadmap was authoritative, listed feature lanes owned by
separate sessions, and pointed Image Studio at airforce.ai. That information is
preserved in Git history but is no longer operational guidance.

## Canonical navigation

| Need | Authority or source |
|---|---|
| Current priority and sequencing | `docs/ROADMAP.md` |
| Mission record / acceptance contract | `docs/ACTIVE_MISSION.md` |
| Authority relationships | `docs/AUTHORITY_MAP.md` |
| Product direction | `docs/NORTH_STAR.md`; current system shape in `docs/ARCHITECTURE.md` |
| Current project status | `docs/PROJECT_STATUS.md` and runtime evidence |
| Decisions | `docs/DECISIONS.md` and `docs/adr/` |
| Image Lab durable execution architecture | `docs/adr/0040-image-lab-flux2-execution-architecture.md` |
| Image Lab historical lifecycle/cost/safety evidence | `docs/plans/image-studio-character-first-architecture-2026-07-28.md` |
| Archived material | `docs/archive/` and archive manifests |

A plan cannot become current work merely by being newer, more detailed, or
marked ready. It must be sequenced by the canonical roadmap after repository
truth and current gates are verified.
