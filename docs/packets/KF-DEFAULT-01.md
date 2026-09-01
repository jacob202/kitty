# KF-DEFAULT-01 — Image Lab names the exact default route before it renders

**Initiative:** `kitty-opens-the-doors-20260831-v4`
**Owner:** builder
**Free or paid:** free
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Backend-only packet. Its visible UI/actionability is owned by a manifest-less interactive companion.

## What Jacob can do after this
The bounded capability in this packet is implemented and proven without creating a parallel system.

## Why this is the next thing
studio_estimate already returns recipe/provider/reason, but its provider-only _exact_model_id() drops the exact FLUX.2 model even though the same module can resolve recipe.execution_target through _iteration_model_id().

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
The Image Lab estimate path already uses image_recipes.auto_route() and returns recipe_id, provider and routing_reason, but gateway/routes/image_studio_jobs.py resolves model_id from provider alone. That resolver knows openrouter, legacy flux and comfyui, but returns null for FLUX.2 even though the selected recipe carries an execution_target that gateway.flux2_targets can resolve exactly; the same file already has the recipe-aware _iteration_model_id() seam used for retry truth. Make studio_estimate use one recipe-aware, no-I/O model-resolution path so a deterministically known route returns its exact model id before dispatch. Preserve a truthful null only for providers whose model genuinely is selected at runtime. Keep auto_route as the single recipe/default authority and preserve its routing_reason verbatim. Do not dispatch a provider, probe the network, add a recipe registry, change spend policy, or change Image Lab frontend state. This packet creates no new files.

## Acceptance criteria
- A FLUX.2 Klein estimate returns recipe_id bfl_flux2_draft, provider flux2, exact model_id flux-2-klein-4b, and the auto_route routing_reason without dispatching a provider.
- A FLUX.2 Pro estimate returns exact model_id flux-2-pro from the recipe execution target rather than null.
- Existing OpenRouter, legacy FLUX and ComfyUI estimate model ids remain compatible.
- A provider whose model is genuinely selected only at runtime may still return model_id null; Kitty does not invent an identifier.
- Explicit recipe preference and the existing auto_route quality/identity/default decision remain the only recipe-selection authority.
- Cost and duration estimation still receive the same selected provider and the newly truthful exact model id, and no network/provider generation call occurs.
- python -m pytest -q tests/test_image_batch_routes.py passes.

## Verification
**Tier 1 — mechanical.** Builder-runnable commands:
  - `python -m pytest -q tests/test_image_batch_routes.py`
  - `python -m ruff check gateway/routes/image_studio_jobs.py tests/test_image_batch_routes.py`

**Tier 2 — running app.** Not applicable to this backend-only half; its manifest-less interactive companion owns the running-app Playwright smoke.

**Tier 3 — product acceptance.** Not applicable to this backend-only half; independent Product Acceptance is required on the user-facing companion before the door is considered finished.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
If exact model resolution requires contacting a provider, changing recipe selection, or changing spend/dispatch policy, stop; this packet is pre-dispatch truth only.

## Recovery
Read-only route-selection code and tests only; no provider call, migration, secret, or durable product-data change.
