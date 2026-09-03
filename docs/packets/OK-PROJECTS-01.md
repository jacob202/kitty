# OK-PROJECTS-01 — Projects Becomes the Continuity Workspace

**Status:** draft candidate; not activated
**Roadmap phase:** 2 — primary surfaces

## Mission
Make Projects the durable place Jacob returns to understand what a project is, what already happened, what matters next, and how to continue it.

## Depends on
- `OK-ACTION-01/02` canonical Project actions/destinations.
- `OK-CONTINUITY-01` relationships where Project/Work/Artifact continuity is required.
- Existing project registry/resume/next-step authorities remain canonical.

## Product acceptance moment
Open a real project after a fresh app start. Its current next step, recent/active work, artifacts/results, deadlines, and useful context are understandable; Jacob can continue, Ask Kitty, open related work/artifacts, update project-facing fields that are already editable, and recover when one source is unavailable.

## Required behavior
- Create/open/select/resume a project without copying an internal ID.
- The Project title/status/current next step comes from the owning Project authority, not a stale Home/Chat projection.
- Show work, artifacts/results, deadlines, and recent relevant activity only when the relationship is authoritative.
- `Continue`/next-step action does something real or explains why no next step is known.
- `Ask Kitty` passes a canonical structured Project reference into Chat.
- Related Work and Artifact links open their canonical destinations with context preserved.
- Renames/updates retain stable identity across reload and other surfaces.
- Source-unavailable is distinct from “project has no data.” Partial project state remains usable.
- Avoid equal-weight dashboard sections; prioritize continuation and decisions.

## Verification
**Tier 1:** Projects/object-action/next-step tests plus changed Gateway tests; add stale-projection and source-unavailable regressions.

**Tier 2:** desktop + iPhone-class running-app scenario: create/open a project, see/perform next action, open related Work/Artifact, Ask Kitty about it, reload, then exercise one degraded source.

**Tier 3:** independent reviewer proves the same Project is recognizably the same object in Projects, Chat, and at least one of Home/Work/Library.

## Non-goals
- A new project store.
- Universal graph/database rewrite.
- Duplicating full Work or Library inside Projects.

## Done when
A Project feels like a resumable workspace rather than a record page, and returning to it after time away gives Jacob a trustworthy “where was I / what now?” answer plus working actions.
