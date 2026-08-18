# ADR 0039 — Kitty owns the canonical product surface

Status: Accepted
Date: 2026-08-17

## Decision

Kitty's native frontend is the canonical user-facing product surface. Open WebUI remains useful reference/commodity software, but it is not the product shell Kitty should design around.

The user should experience one coherent Kitty product with one backend truth. Internal systems such as Gateway, KittyBuilder, LiteLLM, providers, queues, and workers are implementation details unless exposing them helps the user make a decision or verify an outcome.

## Product shape

The default product hierarchy is intentionally small:

- Home / Chat — primary interaction and continuity surface.
- Projects — persistent context for ongoing goals.
- Image Lab — dedicated conversational visual workspace.
- Activity / Builder evidence — durable work state, progress, blockers, results, and proof.
- Settings — models, providers, budgets, integrations, and advanced controls.

This is a product hypothesis to validate through live use, not permission to add navigation for every subsystem.

## Model selection

Model choice remains first-class. The default picker should be curated rather than exhaustive, but must retain enough current information to make an informed choice: exact model, provider when relevant, strengths, capabilities, availability, context limits where decision-relevant, and approximate cost.

The default question is "what are the best serious choices for this job right now?", not "what IDs does the gateway know?" and not "hide the model from the user." Task-aware recommendations may highlight recommended, best-quality, best-value, and fastest-reasonable choices while preserving manual control.

Model metadata must come from canonical backend discovery/registry truth rather than duplicated frontend constants. Claims about quality or latency require evidence; pricing and availability must not be guessed.

## Image Lab

Image Lab is a first-class dedicated workspace, not merely an image button inside ordinary chat. Interaction inside the workspace is conversational so the user can drop images in and describe intent instead of writing provider prompts.

Generated and uploaded images are persistent working objects. The workspace should support selecting and combining references, branching from previous generations, comparing outputs, reusing images as references, and preserving lineage/history.

Generation is durable asynchronous work. 1/2/4-image batches, queue state, cancellation semantics, cost estimates, and duration estimates should be explicit. User-visible estimates must be grounded in known provider pricing or observed execution facts; conservative spend ceilings are not price estimates.

## Backend/frontend contract

The backend owns durable truth. Frontend state renders it and may optimistically improve responsiveness only when it reconciles back to server truth.

Important state machines — Builder work, image jobs/batches, provider availability, model availability, projects, approvals, retries, pauses, failures, and cancellations — must not be collapsed into misleading local booleans.

Reload is a correctness test: after a browser refresh the product should reconstruct the important state from the backend.

## UX principles

- Prefer one canonical workflow over duplicate surfaces.
- Conversation is the control surface; specialized workspaces deepen dedicated work.
- Progressive disclosure: concise result first, detailed evidence/logs on demand.
- Failures answer what happened, whether work was preserved, and what can be done next.
- Dashboard cards answer user questions rather than expose telemetry for its own sake.
- Prefer deletion and boring architecture over abstraction or visual complexity.
- Optimize for reliable AI-assisted maintenance: canonical schemas, obvious boundaries, explicit contracts, and minimal dead code.

## Validation

Completion requires more than unit tests. Cheap agents should use the live product as independent synthetic users with different missions, followed by a smaller adversarial review from stronger product, frontend, backend/state, and reliability perspectives. Repeated confusion is product evidence.

Representative live journeys include conversation continuity, real model selection, Builder execution/evidence, provider failure and recovery, project continuity, Image Lab batching/editing, and refresh/reconnect behavior.

## Consequences

Open WebUI-specific backlog items are not automatically product work. Borrow mature commodity patterns where useful, but do not keep two overlapping product shells without a concrete user-facing reason.

The convergence target is not "finish a frontend." It is: Kitty behaves like one coherent, trustworthy product whose frontend and backend describe the same reality.