# OK-RESPOND-01 — Truthful Interaction Feedback

## Mission

Make every primary user action visibly respond from press through authoritative outcome, with stable geometry and truthful recovery semantics.

## Depends on

- `OK-ACTION-01/02`
- accepted Activity/action lifecycle foundations from the WOW stack
- enough of `OK-PRECISION-01` that loading/control geometry is shared

## Product acceptance moment

Across Home, Chat, Work, Projects, Library, Automations, and Image Lab, click every primary action. Nothing produces a mystery click. The user immediately sees one of:
- navigation;
- queued/running progression;
- waiting for approval/input;
- success;
- failure with recovery;
- truthful unavailable state.

## State grammar

Use domain truth, but normalize presentation where equivalent:

- ready
- queued
- running
- waiting for user
- succeeded
- failed
- partial
- unknown

Do not force a domain to claim one of these if the underlying authority cannot support it; `unknown` is valid.

## Interaction rules

### Press
- pointer/touch/keyboard pressed state is immediate;
- disabled controls do not fire;
- double-submit protection for mutation paths;
- focus remains predictable.

### Pending
- preserve surrounding layout dimensions;
- use inline state/spinner/skeleton appropriate to operation duration;
- keep cancellation/stop only if the owning workflow supports it;
- do not hide the object while it is working.

### Approval
- approval card shows meaningful exact arguments;
- approving is not equivalent to successful execution;
- execution status follows separately.

### Success
- reflect the authoritative result;
- expose produced Artifact/result/destination where relevant;
- do not toast-and-forget a durable result that should remain on the object.

### Failure
- preserve failed context;
- describe what failed in product language;
- expose retry/recovery only when real;
- distinguish failed from unknown/ambiguous outcome.

### Navigation
- immediate selected/navigation feedback;
- destination should preserve object/project context when possible;
- Back returns predictably.

## Motion

Motion clarifies state changes only.
- no decorative idle animation;
- no long transitions that make Kitty feel slower;
- `prefers-reduced-motion` collapses nonessential motion;
- status/result insertion should not cause large layout jumps.

## Verification matrix

Exercise at least one primary action per surface:

- Home
- Chat
- Work
- Projects
- Library
- Automations
- Image Lab

For async domains, exercise successful and failed/degraded paths where practical.

## Tests

- double submit blocked;
- pending state rendered;
- approval != execution success;
- unknown != failed;
- produced result remains discoverable;
- retry only displayed when supported;
- focus/keyboard activation;
- reduced motion flag respected by shared motion primitive.

## Non-goals

- New toast framework unless current one is genuinely insufficient.
- Fake progress percentages.
- Globally optimistic mutations.
- Replacing ActivityCenter.

## Done when

Primary actions across the verification matrix have no silent or misleading transition in running-product acceptance.
