# Autonomy v2 Design

## Goal
Make KittyBuilder self-maintaining enough to run unattended without widening its authority.

## Constraints
- One existing Builder queue and one launchd supervisor only.
- Free execution remains the default; no new paid routing.
- No automatic retry grants, push, PR creation, merge, or product decisions.
- Builder durable queue/attempt/run state remains execution authority.
- GitHub/current-main reconciliation is read-only evidence, not a second state store.

## Architecture
Autonomy v2 adds a read-only truth layer around the existing Builder kernel and deterministic admission gates inside it. The supervisor reconciles current main/GitHub before launch, performs path-aware stale-base preflight, then dispatches only packets whose durable state and external reality agree.
## Components
1. **Truth + freshness:** one bounded `gh pr list` snapshot plus one fresh `origin/main` SHA per tick; flag open/merged Builder branches and path-overlapping stale packet bases. A snapshot that reaches its safety limit is treated as incomplete, never authoritative. External lookup failure is reported but does not invent state.
2. **Deterministic contract checks:** packets may declare literal `forbidden_symbols`, `required_symbols`, and `forbidden_paths`. These are persisted with the immutable packet and checked after trusted parent commit, before validation/reviewer spend.
3. **Runway:** expose counts for runnable backend, running, held/paused, operator-blocked, publication-ready, and unresolved total. Low-water is based on actionable work, not raw initiative count.
4. **Refill:** produce a deterministic, non-mutating refill request when actionable runway falls below six. It names live evidence and required candidate fields; it never applies a manifest.
5. **Publication inbox:** project reviewed/publishable work into one read-only list so publication is a single operator decision surface. Supervisor status can scope runway/inbox by initiative prefix so one campaign never inherits historical Builder experiments.

## Failure behavior
- Relevant stale base: skip dispatch with a named preflight reason.
- Existing open/merged PR for the same Builder branch: skip duplicate execution.
- Contract-check violation: deterministic failed attempt, repairable when the worker tree is still valid repair input.
- GitHub unavailable or PR snapshot incomplete: fail closed before worker dispatch and report the reconciliation blocker.
- Fresh-main lookup unavailable: fail closed before worker dispatch rather than admitting work against stale code.
- Empty/low runway: return a refill request, never manufacture or apply work.

## Tests
TDD at unit/integration level. Supervisor tests prove no launch on stale/colliding external truth. Initiative tests prove schema/persistence. Loop tests prove contract violations stop before reviewer invocation. Autonomy projection tests prove runway/refill/publication classification and no mutations.