# OK-CHAT-02 — Concierge Injection + Provenance

## Mission

Inject the bounded product context from `OK-CHAT-01` into Chat in a way that is useful to the model, explicit about provenance/degradation, and impossible to confuse with user-authored text.

## Depends on

- `OK-CHAT-01`
- accepted WOW context-reference/context-assembler foundations

## Product acceptance moment

With an active Project, relevant running Work, one recent Artifact, and a near Deadline, ask Chat for guidance. Chat uses those facts without claiming access to unavailable sources, and the response can render/open the exact referenced Kitty objects.

## Rules

- explicit user-attached/context references rank highest;
- active Project context is next;
- `needs_you`/running/upcoming state is injected only within hard caps;
- passive history is lower priority;
- provenance labels distinguish authoritative source data from derived ranking;
- degraded source reads are represented as degraded, not empty;
- object references remain structured enough for rendering/action attachment;
- invisible implementation IDs never become the primary user-facing wording.

## Context assembler integration

Prefer extending the single existing deep context assembler rather than adding a parallel chat-only prompt builder.

The assembler should remain the place that:
- enforces total context budget;
- records truncation/degradation warnings;
- produces evidence/provenance for the request;
- keeps memory retrieval separate from product-state projection where useful.

Do not append unbounded JSON blobs to the system prompt.

## Model-facing representation

Use compact structured blocks. Example shape only:

```text
<kitty_product_context>
Active project: School — status active — ref project:12
Needs you:
- Builder review waiting — ref work:...
Upcoming:
- Assignment due 2026-09-04 — ref deadline:...
Recent result:
- Research report — ref artifact:...
Source health: projects=ok work=ok deadlines=ok artifacts=degraded
</kitty_product_context>
```

Keep full content behind explicit references/artifact retrieval rather than injecting everything by default.

## Provenance / evidence

Request/response evidence should make it possible to answer:
- which product sources were queried;
- which succeeded/failed;
- which objects were actually included after ranking/budgeting;
- which explicit user references were resolved;
- which context was clipped.

Do not expose noisy internal telemetry in normal UI; preserve it for evidence/disclosure.

## Tests

- explicit reference survives and outranks inferred object;
- source degradation marker survives context clipping;
- max total product context cap holds;
- injected object IDs/types correspond to canonical references;
- model prompt never receives missing-source state as an empty authoritative list;
- user-visible message remains clean of hidden context markers after render;
- retry/reload preserves explicit reference identity.

## Non-goals

- broad memory rewrite;
- new model router;
- automatic mutations;
- exposing full Artifact content unless explicitly selected/retrieved;
- universal object search implementation.

## Done when

Chat has a single bounded, evidenced, provenance-aware product-context path that can reliably support cross-Kitty guidance without prompt bloat or truth loss.
