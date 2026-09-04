# Primary Product Recovery Candidates — 2026-09-03

**Status:** final product-reality inventory; **not an ordered implementation program**.

**Purpose:** preserve verified product defects and high-leverage repair options without activating them all. This inventory does not own sequencing. `docs/ACTIVE_MISSION.md` and `docs/ROADMAP.md` do; at this closeout they select **BUILDER-001** next. Jacob's existing screenshots/live failures already count as baseline evidence; do not require a week of unusable dogfood before fixing obvious blockers.

## Recovery outcome

The immediate product outcome is simple: **Kitty becomes usable enough that Jacob can stay in it and accomplish ordinary work without immediately falling into broken, stale, misleading, or developer-only machinery.**

The running candidate supplies evidence; the active Mission/ROADMAP decides what becomes active work. If fresh runtime evidence makes the selected sequence wrong, update/reconcile those authorities explicitly rather than silently switching outcomes. The candidate domains below are evidence and options, not a competing order.

## Candidate repair domains

### Product truth and lifecycle

Current evidence shows stale/synthetic/history data competing with user truth across Library, Projects, Automations/activity, and Builder projections. Establish reversible lifecycle/visibility semantics before polishing those screens. Do not auto-delete owner data.

Known evidence includes 132 Library artifact rows pointing at pytest temporary files and a large persisted synthetic web-monitor set producing repeated example/test 404 activity. PR #811 contains **parked salvage** for reversible Chat/Library archive/missing-file behavior; it is not execution authority and must be independently reconciled before reuse.

### Chat and Home reliability

Preserve working recovery behavior while fixing domain-specific truth: actual routed model attribution is dropped, memory-evidence visibility depends on a local smalltalk heuristic, Home over-fetches several projections, and generic failures can still strand the user with "Something went wrong." Measure before changing invalidation/query architecture.

### Work / Builder ordinary-language journey

The desired journey remains ordinary language → understandable proposal → natural-language correction → explicit approval → durable work → understandable progress/cost/blocker/result. Normal use should not require packet IDs, `allowed_paths`, leases, YAML, ports, or terminal commands. Internal machinery stays behind Advanced/Diagnostics.

A separate mechanical enabler may be required: Builder worktrees currently lack frontend dependency/toolchain parity, which pushes vertical work into separate backend/frontend packets.

### Image Lab end-to-end loop

The intended loop is source/reference → character/profile → explicit binding → generation plan/availability/cost → generation → refinement → reuse in Library/Chat. Character reference and edit source must remain distinct. Live generation evidence requires separate spend/provider authorization when applicable.

### Library and Projects

Library must answer what an item is, where it came from, whether the backing file exists, whether indexing succeeded, and what the user can do now. Projects must represent durable projects rather than every task/deadline/decision that happened to become persistent. Lifecycle actions should be reversible.

### Automations

Make scheduled/condition-false/source-failed/action-failed/delivery-failed/unknown/completed states understandable. Retry only when idempotency/outcome evidence makes it safe. Repeated synthetic/test source noise should be classified and archived, not hidden by arbitrary TTL deletion.

### Cross-cutting boundaries

Repair typed API boundaries, runtime projection size, accessibility/mobile behavior, security/privacy, backup/restore, and performance **while the active user journey crosses them**. Do not start separate mega-refactors. Persistence technologies are acceptable when their authoritative/derived lifecycle is explicit; diversity alone is not a reason to consolidate.

### Hidden capability

For Magic, Life Awareness, Council, TELOS, Patterns, Dreams, Chronicle, desktop capture and similar existing subsystems, use one of four dispositions: **INTEGRATE / INTERNAL TOOL / DEVELOPER-ONLY / RETIRE**. "It exists" is not a reason to add a card or destination.

## Selection rule

For each defect discovered in the running candidate:

1. Does it prevent or materially degrade the active user outcome?
2. Is it already owned or implemented elsewhere?
3. Is the apparent defect actually stale/synthetic state rather than missing code?
4. What is the smallest vertical repair that makes the user journey work?
5. What exact running-product evidence will prove the repair?

Only then activate implementation. Adjacent discoveries are captured/handed off without silently becoming competing work.

## Completion rule

A repair is complete when the exact candidate can perform the intended user journey and recover from the failure mode that originally broke it. Tests and PRs are evidence; they are not substitutes for the running result.
