# KF-EASY-01 — Image Lab has one obvious Create path with advanced knobs behind More

**Initiative:** `kitty-opens-the-doors-20260831-v7`
**Owner:** interactive (held)
**Builder manifest:** none
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Interactive/UI packet intentionally held out of execution. Hold reason: KF-DEFAULT-01 is queued in v4. Compile now, but implement after its exact-default contract lands so the UI does not bake in another route decision.

## What Jacob can do after this
Jacob can open Image Lab, give it the image idea/reference, and hit one obvious Create button; expert controls are still there when he asks for them.

## Why this is the next thing
Image Lab exposes multiple quality/identity/count decisions up front even though the backend already auto-routes and explains the selected recipe; KF-DEFAULT-01 is queued to make exact model truth complete.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
Simplify ImageLab’s first-use hierarchy without removing capability. Keep prompt, reference/character context, output preview and one primary Create action visible. Move quality tier, identity strategy, count and route/model detail behind a clearly labelled More/Advanced disclosure, initialized from the backend’s selected default/estimate rather than a duplicated frontend default. The disclosure must still show the chosen recipe/model and routing reason when available. Preserve edit/iterate, character binding, cost estimate and private-content policy flows. Add the smoke file named here.

## Acceptance criteria
- A new Image Lab session presents one obvious prompt/reference → Create path.
- Quality, identity, count and route/model controls remain available under More/Advanced without being required for a normal generation.
- The default selection and “why” come from the Gateway estimate/route contract rather than duplicated frontend logic.
- Existing character, edit/iterate, estimate, cancellation and policy flows remain reachable.
- Desktop and iPhone layouts keep Create visible and do not hide errors behind the advanced disclosure.

## Verification
**Tier 1 — mechanical.** Not run while held. After the hold clears, run:
  - `cd gateway/kitty-chat && npx vitest run tests/ImageLab.test.tsx tests/ImageLabLayout.test.tsx tests/ImageLabRecovery.test.tsx --reporter=dot`
  - `cd gateway/kitty-chat && npx playwright test tests/smoke/image-lab-easy.spec.ts`

**Tier 2 — running app.** Run `gateway/kitty-chat/tests/smoke/image-lab-easy.spec.ts` at desktop and iPhone-14 widths. Exercise the primary happy path, reload where relevant, and one degraded/error path; primary controls must remain visible and unobscured.

**Tier 3 — product acceptance.** An independent reviewer completes the user-visible workflow in the running product at desktop and iPhone-14 widths and records Product Acceptance before merge.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
Stop if the named owning PR/dependency has not landed, if the backend contract is not truthful enough to support the UI, or if the change would create a parallel source of truth.

## Recovery
Frontend state/projection plus tests only. Revert packet-owned UI edits if the authoritative backend cannot support the acceptance contract; never alter durable product data to make the smoke pass.
