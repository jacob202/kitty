# Kitty Planning Index

**Status:** Navigation and disposition index; not a roadmap  
**Updated:** 2026-07-28  
**Roadmap authority:** `docs/ROADMAP_V2.md` (active authority; `docs/ROADMAP.md` superseded 2026-08-08)  
**Active mission:** `docs/ACTIVE_MISSION.md`

`docs/ROADMAP_V2.md` is the only active roadmap (replaced `docs/ROADMAP.md` 2026-08-08). This file exists to point readers
to reviewed plans and to prevent older session plans from silently regaining
authority.

## Operating rule

- Use `docs/ROADMAP_V2.md` for priority and sequencing.
- Use `docs/ACTIVE_MISSION.md` for the current bounded mission.
- Treat every file under `docs/plans/` or `docs/planning/` as supporting
  evidence unless the canonical roadmap explicitly activates it.
- A plan that describes an older repository state must be superseded or
  archived rather than left marked “ready to implement.”

## Reviewed implementation plans

### Image Studio — preserved later-phase direction

**Current plan:**
`docs/plans/image-studio-character-first-architecture-2026-07-28.md`

The reviewed target is a character-first, session-oriented Image Studio for a
persistent fictional adult character (“James”): maximum practical identity
consistency, photorealistic premium finals, localized repair, multi-character
scenes, a private Qwen/open-weight adult lane, safe hosted challengers, honest
ETA, and bounded spending.

This plan is implementation-ready for later sequencing but is **not current
work** until Phase 1 in `docs/ROADMAP.md` exits.

Superseded Image Studio plans:

- `docs/planning/image-studio-character-system-2026-07-24.md` — older repository
  state and provider assumptions;
- `docs/plans/image-runner-and-recipe-cleanup.md` — runner work partially landed;
  remaining capability-truth work moved into the current plan.

### KittyBuilder

- `docs/plans/KITTYBUILDER_DAILY_DRIVER_PLAN.md` — retained as supporting design
  evidence; sequencing belongs to `docs/ROADMAP.md`.
- `docs/plans/feat-kittybuilder-follow-on-roadmap.md` — retained backlog input,
  not an independent roadmap.

### Product experience and coherence

- `docs/plans/KITTY_PRODUCT_EXPERIENCE_V1.md` — retained evidence.
- `docs/plans/KX_COHERENCE_AUDIT.md` — retained audit input.
- `docs/plans/fix-kitty-ui-wiring.md` — partially landed; requires fresh review
  before further execution.
- `docs/plans/fix-council-ux-all.md` — retained backlog input.
- `docs/plans/call-llm-error-contract.md` — retained implementation plan.

## Historical status

The previous contents of this file were a 2026-07-24 session tracker. They
claimed an older roadmap was authoritative, listed feature lanes owned by
separate sessions, and pointed Image Studio at airforce.ai. That information is
preserved in Git history but is no longer operational guidance.

## Canonical navigation

| Need | Authority or source |
|---|---|
| Current priority and sequencing | `docs/ROADMAP.md` |
| Current bounded mission | `docs/ACTIVE_MISSION.md` |
| Authority relationships | `docs/AUTHORITY_MAP.md` |
| Product direction | `docs/NORTH_STAR.md` and `docs/KITTY_PRODUCT_ARCHITECTURE.md` |
| Current project status | `docs/PROJECT_STATUS.md` and runtime evidence |
| Decisions | `docs/DECISIONS.md` and `docs/adr/` |
| Later-phase Image Studio | `docs/plans/image-studio-character-first-architecture-2026-07-28.md` |
| Archived material | `docs/archive/` and archive manifests |

A plan cannot become current work merely by being newer, more detailed, or
marked ready. It must be sequenced by the canonical roadmap after repository
truth and current gates are verified.
