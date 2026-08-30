# QoL Packet 02 — Image Lab Iteration

**Status:** Implementation plan for Jacob approval (not self-authorizing)
**Packet:** `docs/quality_of_life_packets.md` PACKET 02 — IMAGE LAB ITERATION (P0)
**Branch:** `feat/imagelab-iteration-20260823` (worktree `/Users/jacobbrizinnski/Projects/kitty-imagelab-20260823`)
**Base:** origin/main `ad5b4967`

## Objective

Make image generation iterative: Generate → select → modify one thing → regenerate →
compare → continue. A user takes a good image and produces a meaningful variation
without manually reconstructing the original generation.

## Protected-subsystem invariant

Image generation is a **protected subsystem**. This packet may improve UX, reliability,
lineage, and performance but must not silently reduce existing supported generation
capability. Any change to image policy, provider eligibility, private/adult routing,
character identity, or moderation behavior is **out of scope** and requires a separate
explicitly approved packet.

- **Private-adult lane is untouched**: private-adult generation continues through the
  existing approved lane; no loosening/adding/routing-around policy, no
  provider-permission changes, no character-safety semantic changes.

## Required capabilities (per packet)

Every successful generation must support:
1. **Reuse generation** — reproduce the same generation intent.
2. **Retry** — same generation intent, new attempt (NOT "reconstruct approximately what
   the user did"). Where supported: preserve seed for exact retry; otherwise keep
   prompt/config and vary seed (controlled variation).
3. **Duplicate** — new independent copy with the same parameters.
4. **Modify selected parameters** — change one parameter, keep the rest.
5. **Preserve character identity** — retain character reference/profile, identity
   configuration, and anchors; show changed-vs-unchanged parameters.
6. **Preserve provider/model metadata** — the provider, model, and generation
   configuration that produced the original are carried forward.
7. **Preserve lineage** — parent → child links are recorded and visible.

## Existing primitives to reuse (do not rebuild)

| Capability | Existing source | Notes |
|---|---|---|
| Lineage | `image_jobs.parent_id` + `list_children(parent_id)` + `image_gen.py` operation='variation' when parent_id set | parent→child already persisted |
| Generation config preservation | `image_jobs.provider_params_json`, `compiler_params_json`, `model_id`, `provider`, `intent_json`, `plan_id` | carry forward on retry/duplicate |
| Character identity | `image_sessions.ImageSession` (character_id, reference_ids, protected_traits, requested_changes, last_plan) + anchor_job_id/anchor_artifact_id | preserve identity config + anchors |
| Variation/edit | `image_runner.run_edit()`, `read_anchor_artifact(anchor_job_id)` | modify-anchor path exists |
| Session anchor | `clear_anchor(session_id)` (DELETE /studio/sessions/{session_id}/anchor) | existing route |
| Retry worker | `image_runner` retry_paths, `_mark_failed`/`_mark_unknown`, queue columns retry_count/max_retries | reuse; do not add a new scheduler |

## Deliverables

1. **Backend**: a `JobIntent`/`GenerationContext` helper that reconstructs a retry or
   duplicate payload from an existing succeeded `ImageJob` — reads provider, model_id,
   provider_params_json, compiler_params_json, intent_json, parent_id, and (where the
   character session applies) the session's character_id/reference_ids/protected_traits.
   New route(s) under the existing image-studio jobs router:
   - `POST /studio/jobs/{job_id}/retry` — same generation intent, new attempt (seed
     preserved where supported, else controlled variation).
   - `POST /studio/jobs/{job_id}/duplicate` — independent copy with identical params.
   - Existing modify path (run_edit / batch modify) gains explicit changed-vs-unchanged
     parameter reporting.
2. **UI** (`ImageLab.tsx`/`ImageStudio.tsx`/`ImageGenPanel.tsx`): expose Retry, Duplicate,
   and a Modify-one-parameter flow on a selected generation; show a compact diff of
   changed vs unchanged parameters; lineage indicator (parent → child) on each card.
3. **Tests** (RED first) — see below.

## RED tests first

`tests/test_imagelab_iteration.py`:

1. `duplicate` preserves provider, model_id, provider_params, compiler_params, intent.
2. `retry` preserves generation context (same prompt/config) and produces a new job with
   the original as `parent_id`.
3. Character identity survives iteration: session character_id + reference_ids carried to
   the child job.
4. A changed parameter is actually changed (and only that one).
5. Unchanged parameters remain unchanged.
6. Provider/model recorded on the child job.
7. Private-adult lane unchanged: no routing/policy/provider-permission alteration (assert
   existing lane paths still used for adult content; no new bypass).
8. Lineage: child lists under `list_children(parent_id)`; grandchild chains correctly.

## Acceptance

1. RED tests fail before implementation; GREEN after smallest implementation.
2. Narrow tests then wider image-lab slice pass.
3. Retry/Duplicate verified live against a real succeeded job in the running gateway
   (existing dev environment), including the changed-vs-unchanged diff and lineage.
4. No provider routing, policy, or private-adult behavior changed — diff review confirms.
5. Ruff + mypy clean on changed files.

## Deferred / out of scope

- New model/benchmark scoring, new providers, provider policy changes.
- Parameter locking UI beyond what the packet requires.
- Non-image Lab image flows.
