# GenEvolve adaptation review — 2026-07-28

## Source inspected

- Repository: `https://github.com/MeiGen-AI/GenEvolve`
- Pinned read-only source: `23c847c559ccc0f95bbf4b3d8925898463822f4c`
- Local reference: `.slim/clonedeps/repos/MeiGen-AI__GenEvolve/`
- License: Apache-2.0 for code. Model weights, external search, and renderer
  services have separate terms and must not be treated as local-first defaults.

## The useful idea

GenEvolve's valuable boundary is not its large agent runtime. It produces a
small prompt-reference program, then hands it to a replaceable renderer:

```text
user intent → constrained plan {prompt, selected references, rationale}
            → existing renderer/job lifecycle → durable artifact and evidence
```

The planning result is explicit in `genevolve/agent.py:150-171` and finalised
against bounded reference IDs at `agent.py:357-391`. Its static, named skill
files (`genevolve/knowledge_tool.py:19-113`) are a useful way to supply focused
guidance such as layout, text rendering, materials, and count accuracy without
making every generation request depend on an opaque giant prompt.

## Kitty fit

Kitty already has the primitives GenEvolve's design would otherwise add:

| Need | Existing Kitty owner | Evidence |
| --- | --- | --- |
| Durable generation lifecycle and artifacts | `gateway/image_runner.py` + `gateway/image_jobs.py` | `run()` owns terminal job state (`image_runner.py:35-87`) |
| Local character references | `gateway/image_characters.py`, Studio routes | validated reference upload (`routes/extended.py:480-510`) |
| Renderer switching | `gateway/image_backends.py` and existing engine routing | registry interface (`image_backends.py:9-96`) |
| Recipe selection | `gateway/image_recipes.py` | Studio auto-routes by quality/identity (`routes/extended.py:596-636`) |
| User interaction | `gateway/kitty-chat/src/components/ImageStudio.tsx` | current prompt, character, recipe, and error surface |

Therefore, do **not** import GenEvolve's agent, create a second image queue, or
add its CUDA/vLLM/diffusers stack. A small, validated `ImagePlan` can sit before
the existing `/studio/generate` route and attach its plan metadata to the
existing image job/result path.

## Quick alignment repairs first

These fixes are more valuable and lower-risk than a new planning feature:

1. `ImageStudio.tsx:145-150` sends `seed` and `image_count`, but
   `StudioGenerateRequest` (`routes/extended.py:406-414`) accepts neither. The
   current request-model default can silently discard them. Add an explicit
   schema field and either honour it downstream or return a clear unsupported
   error—never pretend a requested seed/count was used.
2. The same request model accepts `reference_ids`, but the generate handler only
   passes `character_id` to `image_runner.run()` (`routes/extended.py:623-630`).
   Either resolve and pass local selected references through the existing
   renderer contract or remove the misleading API field until supported.
3. `image_backends.py` registers ComfyUI and Stability, while
   `image_runner.py:67-87` routes only `comfyui` and `drawthings`. Reconcile the
   user-visible engine list with the actual runner path before exposing new
   renderer choice.

Each repair must have a targeted contract test and a live Studio interaction
proof on the worktree's own running app.

## Safe adaptation sequence

1. Fix the current Studio request/response contract and make failures visible.
2. Add a local-only `ImagePlan` validation boundary: generated prompt,
   user-selected local reference/character IDs, optional recipe, and a finite
   set of curated local guidance tags. It must return provenance and a reason
   for each selected reference.
3. Present the plan for user approval/edit before generation; dispatch only
   through the existing `image_runner` and `image_jobs` lifecycle.
4. Add named, versioned Markdown guidance only for proven recurring failures
   (for example, spatial layout or text rendering). No hidden external search.
5. Evaluate with local fixtures and existing jobs. Provider/renderer changes,
   model downloads, and external retrieval each require their own approval.

## Explicitly reject

- GenEvolve's unbounded ReAct loop, external web/image search, cache under
  `/tmp`, and silent tool-error continuation (`agent.py:314-341`): they violate
  Kitty's local-first, fail-loud, permission-separated boundary.
- Its GPU-only vLLM/CUDA stack and separate Qwen service: operationally heavy,
  outside the current task, and not needed for a useful planning boundary.
- Copying renderer HTTP clients without Kitty's existing health, cancellation,
  job, privacy, and evidence controls.

## Verification requirements

- Request-schema tests prove a supplied seed/count/reference selection either
  changes the durable job payload or receives a clear failure.
- A browser flow on a worktree-launched Kitty shows the plan, chosen local
  references, renderer, job status, cancellation, and final artifact.
- A mock unavailable renderer and malformed reference both produce actionable
  errors, not an empty gallery or fabricated success.
