# Kitty Planning Index

**Status:** Navigation and disposition index; not a roadmap  
**Updated:** 2026-08-18  
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
sequencing remain owned by the active roadmap and mission.

Superseded Image Studio plans:

- `docs/planning/image-studio-character-system-2026-07-24.md` — older repository
  state and provider assumptions;
- `docs/plans/image-runner-and-recipe-cleanup.md` — runner work partially landed;
  remaining capability-truth work moved into later architecture decisions.

### KittyBuilder

- `docs/plans/KITTYBUILDER_DAILY_DRIVER_PLAN.md` — retained as supporting design
  evidence; sequencing belongs to `docs/ROADMAP_V2.md`.
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
| Current priority and sequencing | `docs/ROADMAP_V2.md` |
| Current bounded mission | `docs/ACTIVE_MISSION.md` |
| Authority relationships | `docs/AUTHORITY_MAP.md` |
| Product direction | `docs/NORTH_STAR.md` and `docs/KITTY_PRODUCT_ARCHITECTURE.md` |
| Current project status | `docs/PROJECT_STATUS.md` and runtime evidence |
| Decisions | `docs/DECISIONS.md` and `docs/adr/` |
| Image Lab durable execution architecture | `docs/adr/0040-image-lab-flux2-execution-architecture.md` |
| Image Lab historical lifecycle/cost/safety evidence | `docs/plans/image-studio-character-first-architecture-2026-07-28.md` |
| Archived material | `docs/archive/` and archive manifests |

A plan cannot become current work merely by being newer, more detailed, or
marked ready. It must be sequenced by the canonical roadmap after repository
truth and current gates are verified.
