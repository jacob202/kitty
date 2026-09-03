# OK-IMAGE-01 — Image Lab Completes the Real Create → Refine → Result Loop

**Status:** draft candidate; not activated
**Roadmap phase:** 2 — primary surfaces

## Mission
Turn Image Lab into a complete, understandable creative workspace using the image pipeline Kitty already has, with identity, route, cost, provenance, failure and result truth intact.

## Depends on
- Current ADR 0040 identity/assignment acceptance direction.
- `KF-EASY-01`, `KF-DEFAULT-01`, and `OK-PRECISION-IMAGE` where still applicable.
- Provider/image authority stays in Gateway/image services; frontend does not create a second provider registry.

## Product acceptance moment
Starting from an empty Image Lab, Jacob can add/select a source or character, describe an image/change, understand the plan enough to proceed, generate, compare/select a result, refine it, recover from a provider failure, and later reopen the final result with provider/model/recipe/cost provenance available without provider jargon dominating the normal flow.

## Required behavior
- One obvious Create path; advanced provider/recipe controls stay secondary.
- Source upload/binding and durable character identity are understandable and reversible where existing contracts allow.
- Two-character assignment never silently swaps identities; the ADR acceptance gate remains fail-closed.
- The selected provider/model/route is truthful before spend/generation; cost authorization boundaries stay intact.
- Generation state is durable enough that reload does not turn running/failed into mystery emptiness.
- A failed generation retains prompt/source/plan and offers the real retry/recovery path.
- Results carry provenance: provider/model, recipe/settings needed to reproduce, source/character bindings, cost/receipt when available.
- Select/refine/regenerate uses the existing session/job/result authorities; no client-only history as truth.
- Mobile remains composed for the core path; dense comparison may use a deliberate sheet/lightbox instead of shrinking controls.

## Verification
**Tier 1:** focused Image Lab/session/job/source/character tests and TypeScript. Keep the 2-scenario × 2-provider identity assignment gate where currently authorized/configured.

**Tier 2:** running app at desktop + iPhone-class: source/character → plan → generation → select → refine; one provider failure/retry; reload during a nonterminal job. Paid image generation requires separate explicit authorization; hermetic fixtures may prove UI mechanics but not the final live-provider claim.

**Tier 3:** independent reviewer confirms result identity, provenance, recovery, and no hidden provider/cost surprise on the exact candidate.

## Non-goals
- New image architecture.
- A provider marketplace.
- Broad model experimentation without a bounded benchmark/budget.
- Decorative redesign before the workflow works.

## Done when
Image Lab can be used end to end without a side terminal/script and its creative convenience never outruns identity, cost, provenance, or failure truth.
