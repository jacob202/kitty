# OK-CHAT-03 — Cross-Kitty Typed Objects in Chat

## Mission

Make Chat render canonical Kitty objects as compact live objects with attached actions, so replies stop describing product state only in prose.

## Depends on

- accepted WOW Rich Chat (`ActionCard`, `ArtifactChatCard`, typed-message seam) or merged equivalent
- `OK-ACTION-01/02`
- `OK-CHAT-01/02`

## Product acceptance moment

Chat says a Builder review needs attention and a deadline is approaching. The response contains two compact live objects:

- Work · waiting for you — `Review` / `Open work`
- Deadline · due Friday — `Plan` / `Open project`

If the Work state changes, the object reconciles to the new authoritative state rather than leaving stale prose controls behind.

## Renderer strategy

Do not build one giant generic card.

Use:
- a shared canonical object shell for identity/title/status/actions;
- small domain renderers/adapters where domain information materially changes presentation;
- existing ActionCard/ArtifactChatCard as inputs to refactor/reuse, not code to throw away.

## Initial object types

Support only the types proven by concierge acceptance first:
- Project
- Work
- Artifact
- Deadline
- existing ActionQueue Action

Add Automation/Image/Research after the base grammar proves reusable.

## Compact anatomy

- product-facing type eyebrow/icon
- title
- one-line relevant state/context
- truthful status
- one primary action
- optional quiet secondary actions/details
- canonical source/destination

Hide technical identifiers/provider internals behind disclosure where needed.

## Live reconciliation

Objects representing mutable state must query/refetch the authority rather than freezing the state serialized into assistant prose.

Examples:
- Work waiting -> running -> completed
- Action proposed -> approved -> executing -> executed/failed/unknown
- Artifact processing -> ready/failed

Do not poll aggressively when Activity/query invalidation can provide a cheaper truthful path.

## Accessibility

- section/card has meaningful accessible label;
- primary action reachable by keyboard;
- status has text, not color alone;
- details disclosure reachable on touch and keyboard;
- minimum touch targets follow design system.

## Tests

- each initial object type parses/renders from canonical reference;
- invalid/missing reference degrades to a truthful unavailable object instead of crashing the message;
- state refetch updates same object in place;
- primary action uses shared executor;
- no duplicate domain action handler appears in Chat renderer;
- technical IDs do not dominate visible copy.

## Non-goals

- Markdown replacement for ordinary prose;
- full custom renderer for every backend type;
- storing rendered card state in chat transcript as authority;
- duplicating Activity Center.

## Done when

A normal Chat response can contain useful live Kitty objects from at least Project, Work, Artifact, and Deadline domains and those objects remain truthful/actionable after state changes.
