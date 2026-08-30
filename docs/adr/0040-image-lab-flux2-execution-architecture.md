# ADR 0040 — Image Lab uses FLUX.2-first intent compilation and native references

**Status:** Accepted  
**Date:** 2026-08-18  
**Supersedes:** the model/mechanism selections in `docs/plans/image-studio-character-first-architecture-2026-07-28.md` where they conflict with this ADR. That document's durable lifecycle, cost-discipline, evidence, consent, and safety framing remains applicable where not superseded.  
**Extends:** ADR 0028 (commodity software precedence), ADR 0032 (evidence-backed claims), ADR 0039 (Kitty native product surface).

## Context

The July 28 Image Studio plan correctly established a character-first, session-oriented product, a dual hosted/private execution boundary, durable job truth, cost discipline, measurable identity evidence, and an intent-to-renderer seam. Its model and identity-mechanism recommendations were based on the image ecosystem available at that time.

By August 18, FLUX.2 exposes generation, native instruction editing, and multi-reference conditioning in the same model family. FLUX.2 [klein] 4B is available as open weights under Apache-2.0 and fits a 24 GB-class GPU. Hosted FLUX.2 [pro]/[max] provide higher-quality final tiers. The official Black Forest Labs skill repository publishes current prompting and API guidance, including multi-reference usage, structured prompting, preservation language, and the fact that native FLUX prompting does not require a negative-prompt field.

Kitty also already has the valuable product-specific spine: durable image sessions, approved plans, jobs, budget reservation/reconciliation, artifacts, lineage, a bounded image agent, a hidden ComfyUI worker, and provider adapters. The goal is to converge these pieces, not build another image stack.

## Decision

### 1. FLUX.2 is the primary Image Lab model family

The initial execution family is:

- **Draft / AutoCreate:** FLUX.2 [klein] 4B through a hosted adapter when the request is eligible for the hosted lane.
- **Safe final:** FLUX.2 [pro] initially, with [max] available as a benchmark challenger rather than a parallel architecture.
- **Editing / repair:** native FLUX.2 instruction editing through the same semantic compiler.
- **Private lane:** FLUX.2 [klein] 4B open weights through Kitty's hidden worker infrastructure.

This is a family-level architecture decision, not a permanent provider lock. Provider choice remains replaceable behind adapters.

### 2. Native reference conditioning is the v1 identity mechanism

Character identity, multi-character composition, outfits, locations, objects, style, pose, and body references are represented as typed references and compiled into the model's native reference inputs.

Identity LoRA, PuLID, InstantID, IP-Adapter FaceID, face compositing, and face-inpaint/denoise pipelines are **not prerequisites** and receive no v1 implementation work. They may return only if the acceptance benchmark demonstrates that native references cannot meet Kitty's likeness or preservation bar.

This ADR deliberately does **not** claim that native references have already solved identity. That is an empirical acceptance question.

### 3. Kitty owns a provider-neutral ImageIntent

The durable user-approved contract is `ImageIntent`, not a provider prompt or provider request body.

At minimum it carries:

- schema version and user goal;
- cast slots and typed reference bindings;
- structured scene / subject / style / technical / color intent;
- protected traits and requested changes;
- operation (`txt2img` or `edit`) and anchor lineage;
- content lane and consent basis;
- quality tier, output count, privacy, and cost ceiling.

BFL's published structured-prompt shape is a useful semantic influence for scene/subject/style/technical/color fields, but BFL wire JSON is **not** Kitty's canonical schema.

### 4. One semantic compiler, multiple transport adapters

A versioned compiler, beginning with `flux2@1`, turns `ImageIntent` into a provider-independent compiled FLUX.2 request:

- flattened positive prose;
- ordered reference bindings and their intended roles;
- preservation/edit instructions;
- seed and generation settings;
- compiler version and known constraints.

Transport adapters then serialize that semantic result for each execution route. BFL Direct, Runware, and the private worker do not have identical request shapes; this difference belongs in transport adapters rather than leaking into user intent.

The user never writes provider prompts. The compiled prose may be inspected in the plan preview.

### 5. Negative intent is normalized semantically

Kitty's historical `negative_prompt` data must never be silently discarded. `flux2@1` converts negative constraints into positive/descriptive constraints by default, following the official FLUX guidance.

A transport such as Runware may expose an additional provider-specific negative-prompt control. That is an optional adapter optimization only if benchmark evidence shows value; it must not change the meaning of the user's intent across providers.

### 6. Variation is structural, not prompt paraphrasing

`VariationStrategy` expands one approved intent into N intents by changing unlocked structured dimensions. Locked identity/reference fields remain invariant. Candidate plans, seeds, compiler version, estimated cost, and actual outcomes are persisted.

Default modes are conservative, balanced, and exploratory. The UI presents a concise variation preview before dispatch and exposes deeper controls progressively.

### 7. Preserve the existing durable Image Lab spine

Keep and extend rather than replace:

- `image_sessions` and their turns, anchor, protected traits, requested changes, and budget accounting;
- `image_plans` as the record of what was approved;
- `image_jobs` as the record of what actually ran, including parent lineage;
- artifact persistence and provenance;
- the authenticated, allowlisted, hash-pinned private worker boundary;
- provider cost reservation/reconciliation and fail-loud state transitions.

The target lineage is generation → variation/edit → repair/upscale without creating a second gallery, queue, or history store.

### 8. Content-lane routing fails closed

Every executable image intent declares a content lane and consent basis before dispatch. Work designated for the private lane must be impossible to route to a hosted adapter through fallback, retry, or provider substitution.

The product policy may be stricter than any provider's current public policy. Hosted policy and moderation behavior are external, mutable facts and must not be inferred from model capability. The private lane is for tightly scoped, consented use defined by Kitty policy; no minor sexual content and no non-consensual intimate or likeness use are permitted.

Keyword guessing is not an authorization boundary.

### 9. Vendored model guidance is an upstream dependency, not Kitty folklore

Use the official `black-forest-labs/skills` FLUX image best-practices material as pinned, attributed compiler guidance rather than re-authoring model-specific prompting rules throughout Kitty.

The upstream README currently states MIT, but the repository does not expose a root `LICENSE` file. Record the pinned commit and the upstream license assertion with the vendored material and re-check license provenance before any commercial distribution. The guidance must remain replaceable.

### 10. RunPod endpoint type is an implementation choice, not an architecture decision

The existing Kitty worker is a custom HTTP service with worker-local upload/job/status state, so a load-balancing endpoint with `workersMax=1` can be a fast compatibility path.

Do not make that workaround permanent architecture. RunPod queue-based Serverless already provides asynchronous submit/status/cancel/retry semantics, buffering, and automatic retry behavior that map naturally to Kitty's durable image jobs. During private-lane bring-up, compare:

1. minimum-change load-balancer reuse of the existing worker; and
2. a thin queue-handler adaptation that lets RunPod own commodity endpoint queuing while Kitty retains product truth.

Choose the option that deletes more worker-local orchestration without weakening Kitty's unknown-outcome, provenance, cancellation, and budget invariants.

## Evidence / benchmark gates

The following remain **unproven until Kitty-specific acceptance work runs**:

1. Native 1–4 reference conditioning meets Jacob's likeness bar for a recurring character.
2. Two recurring identities stay correctly assigned in a one-pass scene.
3. Native instruction editing preserves protected regions well enough to avoid a default mask/inpaint pipeline.
4. [klein] 4B is photorealistic enough for finals, or whether [pro], [max], [klein] 9B, or a challenger is required.
5. The self-hosted 4B lane technically supports the required private workflow on Kitty's actual worker/GPU environment.
6. A separate `body` reference type measurably improves control enough to justify product surface area.

The acceptance benchmark is a decision tool, not a leaderboard. Blind Jacob preference is primary; automated face/preservation measures are advisory evidence and must fail closed when they cannot score reliably.

Run the benchmark as soon as the compiler, one hosted FLUX.2 adapter, and the minimum typed-reference/cast path needed for Q1–Q3 exist. Do **not** fully build Character Pack v2, LoRA machinery, regional editing, or broad recipe complexity before those results are known.

## Immediate correctness defect

As of repository `main` at `7badd7e1b08dfc49cf1c0dc3ae3a7f75eed42fa2`, and still on product-surface PR #528 head `23e4a02f967289676d301d44e021d9622a8c1c99`:

- `image_agent` can decide `operation="img2img"` and bind an anchor;
- `image_plans.StoredPlan` does not persist `operation` or `anchor_job_id`;
- `/studio/generate` hardcodes recipe routing to `operation="txt2img"` and calls `image_runner.run()`;
- `image_runner.run_edit()` exists but therefore has no production dispatch from the approved-plan route.

Commit `5b08b67e8cc83b567332ee87b80ad0950cdd76f6` contains a focused red test for this contract, but that commit is not in current `main` or current PR #528 history. Recover or recreate the test against the current branch; do not claim it is already active.

This is the first implementation action because the current UI can describe an edit while the dispatch path performs a new generation.

## Implementation sequence (dependency order, not a roadmap)

1. **IL-01 — approved edit truth:** persist operation + anchor, validate session ownership, dispatch approved edits through the edit executor; recover/recreate the focused red test.
2. **IL-02 — fail-closed lane contract:** content lane + consent basis enforced at the runner/executor boundary so fallback cannot leak private work to hosted providers.
3. **IL-03 — `flux2@1` semantic compiler:** pinned upstream guidance, deterministic golden cases, ordered references, preservation instructions, compiler version on jobs.
4. **IL-04 — hosted FLUX.2 transport(s):** klein draft + pro final, multiple references, typed moderation/refusal outcomes, estimate before spend and actual reconciliation after.
5. **IL-05-min — minimum typed references + cast:** enough Character/reference binding to execute Q1–Q3 without overbuilding the Character Pack.
6. **Benchmark gate:** run the acceptance set and adjudicate identity, two-character, edit-preservation, and final-tier choices.
7. Only after the gate: deepen Character Pack, AutoCreate/VariationStrategy, private-worker adaptation, executable recipes, lineage/history affordances, and deletions.

## Consequences

- Kitty has one image intent language and one FLUX.2 semantic compiler, not one prompt stack per provider.
- Hosted and private routes can share user-facing semantics without pretending their wire protocols are identical.
- Existing durable state remains authoritative; model/provider integrations become replaceable adapters.
- Native model capability deletes a large amount of planned identity/edit glue unless benchmark evidence proves it necessary.
- Image Lab implementation can proceed vertically: correctness first, then modern reference/edit capability, then benchmark, then only the complexity that earns its place.
