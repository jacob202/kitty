# Salvage 01 — local ComfyUI identity conditioning

## Decision

**Adapt the old FaceID graph into the existing `mcp/imagen` engine boundary. Do not copy the old scripts.**

The useful missing capability is not “identity consistency” generally. Current Kitty already has substantial identity infrastructure:

- `mcp/imagen/character_lock.py` — exact single-reference locks with SHA-256 verification and fail-closed behavior.
- `mcp/imagen/face_match.py` — InsightFace reference embedding and candidate scoring.
- `mcp/imagen/benchmark.py` — exact-reference identity benchmark.
- `mcp/imagen/engines/runware.py` — cloud FLUX + PuLID identity conditioning.
- `mcp/imagen/engines/fal.py` — cloud FLUX PuLID identity conditioning.
- `mcp/imagen/engines/nano_banana.py` — reference-conditioned generation/compositing.
- `mcp/imagen/engines/comfyui.py` — local/no-API-cost generation, but it currently ignores `identity_images`.

The actual gap is: **the local ComfyUI engine cannot honor the same locked identity contract that the cloud identity engines can.**

## Historical evidence

Primary source paths:

- `/Users/jacobbrizinnski/Projects (from backup)/imagegen/gen_face_final.py`
- `/Users/jacobbrizinnski/Projects (from backup)/imagegen/generate_my_face_auto.py`

The May workflow proved the shape of a working SD1.5 graph:

1. `CheckpointLoaderSimple`
2. `IPAdapterModelLoader` using a FaceID adapter
3. `IPAdapterInsightFaceLoader` using an InsightFace model
4. `LoadImage` for one identity reference
5. `IPAdapterFaceID` to condition the diffusion model
6. normal positive/negative conditioning
7. `KSampler`
8. `VAEDecode`
9. `SaveImage`

Historical tuning values included roughly:

- identity weight: `0.9`
- FaceID-v2 weight: `1.3`
- embedding scaling: `V only`
- conditioning window: full generation

These are **starting hypotheses for a benchmark**, not values to copy blindly. Node APIs and model versions may have changed.

## Why not restore the script

The old scripts hard-coded:

- absolute user paths;
- checkpoint and adapter filenames;
- ComfyUI node assumptions;
- prompt content;
- polling behavior;
- identity reference selection.

They also bypass current character locks, engine contracts, benchmark receipts, retries and error semantics.

Restoring them would create a parallel ImageGen path.

## Modern adaptation

### Engine contract

Extend `ComfyuiEngine.generate_async(..., **kwargs)` to explicitly inspect:

`identity_images = kwargs.get("identity_images")`

Rules:

1. no identity image -> preserve current workflow exactly;
2. exactly one identity image -> use the local identity-conditioned workflow;
3. zero/missing file, multiple identity images, unavailable custom nodes, unavailable adapter/model, or failed reference upload -> **fail closed**;
4. never silently fall back to unconditioned generation when identity was requested.

This matches the behavior already used by current cloud identity engines.

### Workflow boundary

Prefer a dedicated builder such as:

`_wf_sd15_faceid(prompt, params, reference_handle, capabilities)`

rather than branching large chunks inside `generate_async`.

Keep model/node names configurable. The historical filenames are evidence of what worked once, not durable configuration.

### Capability probe

Before generation, verify the live ComfyUI instance supports the required nodes and configured models. A bounded `/object_info`-style probe is preferable to discovering missing nodes after a long generation attempt.

Required capability should be explicit in the result:

- `identity_conditioning=available`
- or a concrete fail-closed reason.

### Reference handling

Do not assume `LoadImage` may read arbitrary absolute host paths.

Use a single supported reference-ingress method:

- upload/copy the locked reference into ComfyUI's input namespace; then
- pass the returned/safe input name into `LoadImage`.

Bind the generation receipt to the existing locked-reference SHA-256 so the generated result can prove which identity reference was used.

### Evaluation

Reuse current evidence:

- `CharacterLock`
- `FaceMatcher`
- `mcp/imagen/benchmark.py`

A proving experiment should compare matched seeds/prompts where feasible:

1. current unconditioned local ComfyUI;
2. local ComfyUI + FaceID candidate;
3. an already-supported identity backend as a reference point when cost/availability permits.

Do not declare success from visual impression alone. Record exact reference hash, model/config identity, seed, prompt hash, candidate image and face-match score.

The current benchmark threshold is evidence about the existing harness, not a permanent product threshold. Keep it configurable and evaluate false positives/false negatives before tightening acceptance.

## Tests before live generation

Unit tests should require no local model download:

- one identity image inserts the identity nodes and routes the sampler through the conditioned model;
- no identity image preserves the existing graph;
- more than one identity image rejects;
- missing reference rejects;
- missing node/model capability rejects;
- requested identity never silently becomes unconditioned generation;
- receipt/reference identity remains bound to the locked SHA.

## Non-goals

- no second character store;
- no replacement for Nano Banana, Runware or Fal;
- no new Image Lab authority;
- no automatic “best provider” change;
- no multi-person identity support in the first slice;
- no resurrection of old personal prompt presets.

## Smallest useful implementation packet

**Outcome:** current `mcp/imagen` can run one existing locked character through local ComfyUI identity conditioning, fail closed when unsupported, and score the result through the existing benchmark.

Likely implementation surface, to be revalidated at execution time:

- `mcp/imagen/engines/comfyui.py`
- focused ComfyUI engine tests
- perhaps one narrowly scoped config field for adapter/model names
- existing benchmark only; do not create a second benchmark framework
