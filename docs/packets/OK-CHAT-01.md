# OK-CHAT-01 — Bounded Kitty Concierge Context

## Mission

Give Chat a bounded, truthful read projection of the rest of Kitty so it can guide the user across Projects, Work, Artifacts, Deadlines, Automations, and Image Lab without becoming a second owner of any of those systems.

## Important base rule

Do not implement this packet from an old baseline if the prior WOW campaign branches are still pending integration. In particular, first reconcile or base on the current equivalents of:

- `feat/wow-rich-chat-20260831`
- `feat/wow-context-picker-20260831`
- `feat/wow-project-workspace-20260831`
- `feat/wow-activity-center-20260831`
- `feat/wow-artifact-canvas-20260831`

Those branches already introduce durable action/artifact cards, context references, project workspace, activity projection, and artifact preview concepts that this packet should reuse rather than duplicate.

## Product acceptance moment

Ask Chat: `What should I deal with next?`

A truthful response can use current Kitty state to mention, for example:

- an active Project and its next step;
- Work that is running or waiting for the user;
- a recent Artifact relevant to the active Project;
- an approaching Deadline;

and can attach canonical Kitty object references/actions so the user can act without copying IDs or hunting through navigation.

## Principle

Chat receives a **projection**, not unrestricted database/store dumps.

The projection should answer:

1. What context is active?
2. What currently needs the user?
3. What is actively running?
4. What has recently completed that is relevant?
5. What is approaching soon?
6. Which canonical Kitty objects support those facts?

## Existing capability to reuse

Verify current repo state before coding, especially:

- `gateway/context_assembler.py`
- `gateway/context_references.py` if integrated
- activity projection/routes if integrated
- Project context/resume endpoints
- ArtifactStore/Library projections
- Deadline projections
- Automation state
- Image job/session/result state
- existing chat request assembly
- existing ActionCard / ArtifactChatCard / typed-message seams

Do not rebuild any of these under a new `concierge` store.

## Proposed projection

Names are illustrative.

```json
{
  "active_context": {
    "project": null,
    "conversation": null,
    "explicit_references": []
  },
  "needs_you": [],
  "active_work": [],
  "recent_results": [],
  "upcoming": [],
  "relevant_objects": [],
  "generated_at": "...",
  "source_health": {}
}
```

Each projected entry should preserve its owning authority and canonical object identity/action shell from `OK-ACTION-01` when available.

## Ranking / boundedness

The context must be intentionally small.

Recommended rules:

- explicit `@`/attached context wins;
- active Project context ranks next;
- `needs_you` outranks passive recent history;
- near deadlines outrank distant ones;
- active/running work outranks old completed work;
- recent Artifact/result relevance can use Project relationship and recency;
- do not dump global Memory/Library text into every chat turn;
- technical system health should appear only when it explains degraded capability or is explicitly requested.

Define hard count/size caps and test them.

## Provenance

The model-facing representation must make source and state clear enough that Chat can distinguish:

- authoritative current state;
- derived/ranked context;
- unavailable/degraded source;
- user-explicit reference;
- inferred relevance.

## Execution boundary

This packet is read/context only.

Actions offered in Chat must flow through the canonical action renderer/executor and owning routes. The context projection itself must not mutate anything.

## Failure semantics

If one source is unavailable:

- keep the rest of the context usable;
- expose the source as degraded/unknown where material;
- never reinterpret missing source data as `none exist`;
- do not tell the model a failed read means the user has no deadlines/work/artifacts/etc.

## Tests

Cover at least:

1. Explicit object reference beats inferred context.
2. Active Project state is included and bounded.
3. `needs_you` outranks passive completed history.
4. A failed source is represented as degraded, not empty truth.
5. Projection size/count caps hold under large fixture data.
6. No mutation occurs while building context.
7. Canonical object identities survive into model-facing context.

## Non-goals

- New memory architecture.
- Full universal search.
- Automatic consequential actions.
- Home redesign.
- Research-specific deep source ingestion.
- Passing all raw provider/debug metadata to the model.

## Done when

Chat has one tested bounded product-context input that composes existing Kitty authorities and can truthfully support guidance across at least Project + Work + Artifact + Deadline state.
