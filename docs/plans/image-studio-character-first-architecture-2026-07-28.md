# Image Studio Character-First Architecture — 2026-07-28

**Status:** Reviewed later-phase implementation plan; not authorized current execution  
**Roadmap authority:** `docs/ROADMAP.md` and ADR 0020  
**Primary use case:** Persistent fictional adult character generation (“James”) with maximum practical likeness, photorealistic final output, localized editing, multi-character scenes, and lawful fictional-adult NSFW support  
**Research date:** 2026-07-28  
**Evidence convention:** **VERIFIED** = directly established from current repository code, official documentation, or a cited current benchmark. **INFERENCE** = engineering conclusion derived from verified evidence. **HYPOTHESIS** = requires Kitty-specific implementation or benchmark proof.

---

## 1. Executive decision

Kitty should not choose one universal image model and should not optimize final renders for the lowest raw image price.

The target architecture is a **character-first, session-oriented, dual-lane system**:

1. **Hosted general lane** for safe drafting, safe premium finals, typography, and independent benchmark challengers.
2. **Private open-weight lane** for the fictional-adult James workflow, identity LoRAs, controlled multi-reference generation, regional editing, and explicit adult content.

Both lanes must use the existing durable `image_jobs` lifecycle. They must not create a second queue, gallery, or artifact history.

### Recommended starting stack

| Role | Initial recommendation | Why | Confidence |
|---|---|---|---|
| Safe draft / composition | Gemini 3.1 Flash Image | Strong multi-reference and conversational editing at a predictable price; up to four character references | **VERIFIED candidate** |
| Safe premium final | GPT Image 2, challenged by Gemini 3 Pro Image and FLUX.2 max | GPT Image 2 currently leads broad human-preference leaderboards; Kitty must still benchmark its own portrait and edit tasks | **VERIFIED candidate; selection requires benchmark** |
| Safe precision edit | GPT Image 2 or FLUX.2 max | Both expose image editing; FLUX.2 supports several references and up to 4 MP | **VERIFIED candidate** |
| Explicit fictional-adult draft | Qwen-Image-2512 at reduced steps/resolution | Apache-2.0 open weights, improved human realism and natural texture, no hosted-policy dependency | **VERIFIED base; quality requires benchmark** |
| Explicit fictional-adult final | Qwen-Image-2512 + versioned James LoRA + benchmark-selected adult photoreal adapter/checkpoint | The final stage should spend compute on the best proven James configuration, not the cheapest model | **INFERENCE** |
| Explicit localized repair | Qwen-Image-Edit-2511 with masks, per-character references, and saved seed/context | Officially supports multiple images and improved single- and multi-person consistency | **VERIFIED candidate** |
| Explicit visual critic | Local Qwen3-VL variant, plus deterministic identity/preservation metrics | Keeps explicit images off providers that prohibit or may reject them | **VERIFIED model family; critic accuracy requires benchmark** |
| Orchestration | ComfyUI only for the open-weight lane; direct SDK/API adapters for hosted models | ComfyUI is valuable for LoRA, masks, ControlNet-style composition, and custom workflows, but unnecessary overhead for hosted APIs | **INFERENCE** |
| GPU hosting | Scale-to-zero RunPod Serverless Flex first; Modal as a clean-code challenger | Both charge actual compute; RunPod has queue endpoints, GPU fallbacks, execution timeouts, and zero minimum workers | **VERIFIED candidates** |

### What Kitty should stop doing

- Stop presenting `SDXL Photonic`, PuLID, Draw Things, or other registry entries as operational merely because a recipe row exists.
- Stop using the cheapest model as the automatic final model.
- Stop treating one primary reference image as a complete identity system.
- Stop appending one generic “enhanced prompt” and calling that model adaptation.
- Stop full-image rerolls when a localized edit can preserve the successful regions.
- Stop treating FLUX.1 Kontext as the current default candidate; FLUX.2 is the current BFL family.
- Stop treating persistent GPU rental as the default. Kitty’s expected personal workload is bursty, so idle billing is waste.
- Stop claiming “100% likeness.” The product should promise measurable consistency, visible evidence, and repair—not mathematical perfection.

---

## 2. Corrected product objective

The immediate Image Studio design target is not a generic art generator. It is:

> Given a versioned fictional adult Character Pack and a natural-language request, create a small number of highly photorealistic final images that preserve the character’s identity, anatomy, textures, and scene intent; support multiple recurring characters; permit precise localized repair; retain session knowledge; and route lawful fictional-adult explicit work through private infrastructure.

The optimization order is:

1. final-image quality on James use cases;
2. identity stability across a session;
3. successful-result cost, including failed attempts and repair;
4. localized-edit preservation;
5. multi-character controllability;
6. reliability and honest progress;
7. speed;
8. integration and operating burden;
9. provider replaceability;
10. raw per-image price.

Cheap drafts and expensive finals are not contradictory. They are the correct workflow.

---

## 3. Current Kitty audit

### 3.1 What is real and worth retaining

**VERIFIED — durable job foundation**

`gateway/image_jobs.py` provides a provider-neutral SQLite record with Kitty-owned IDs, explicit lifecycle transitions, prompts, seeds, model and sampler metadata, workflow hashes, provider diagnostics, output paths, lineage, priorities, and retry fields. This is the correct substrate. Extend it; do not replace it.

**VERIFIED — character and reference persistence**

`gateway/image_characters.py` already provides:

- private-by-default characters;
- up to six stored references;
- primary-reference designation;
- optional face embeddings and embedding-model metadata;
- tags, versioning, supersession, and gallery records.

This invalidates older planning claims that characters have no references or embeddings. The store should be migrated forward rather than recreated.

**VERIFIED — runner boundary**

`gateway/image_runner.py` owns lifecycle dispatch and keeps route handlers from directly driving engines. Its terminal-state invariant is useful.

**VERIFIED — recipe capability vocabulary**

`gateway/image_recipes.py` contains a useful vocabulary for operations, quality tiers, reference types, inpainting, variation, upscaling, required models, required nodes, and license notes. That vocabulary can survive.

**VERIFIED — ImagePlan direction in PR #289**

PR #289 introduces a user-reviewable plan-to-renderer boundary and validates local references before dispatch. The architectural boundary is correct and should be retained if the PR is repaired and merged.

### 3.2 What is partial, misleading, or disconnected

| Area | Verified state | Required disposition |
|---|---|---|
| Character references | The store accepts several references, but generation selects only the primary or first reference | Retain store; add roles, quality scores, sets, and multi-reference compilation |
| Identity generation | `generate_with_character()` uses one IP-Adapter reference and a scalar weight | Replace with versioned identity strategies and benchmarked workflows |
| IP-Adapter setup | Code comments say the installed adapter is SD1.5 while the workflow is SDXL | Health check must fail loudly; remove “ready” claims until model/node compatibility is proven |
| Recipes | Recipe is recorded but `image_runner.run()` says it is not used for workflow selection | Convert recipes into executable, versioned adapters or mark them unavailable |
| Multi-character | Registry has `max_characters`; current active paths are effectively single-character | Treat as unimplemented |
| Editing | Job schema recognizes inpaint/img2img, but no complete Studio mask/edit lifecycle was verified | Build as a first-class operation, not a prompt trick |
| Progress | ComfyUI polling exists, but no honest stage model, cost ledger, or learned ETA | Add stage events and historical duration estimates |
| Critique/repair | No generated-image critic and no controlled repair loop were verified | New bounded subsystem |
| Session continuity | Gallery and job lineage exist, but there is no explicit image session that carries selected refs, best attempt, defects, or budget | Add session/attempt records |
| `ImagePlan` in PR #289 | Flat prompt, one character, one selected path, generic appended guidance | Deepen into an Intent Contract and model-specific compiler |
| Existing plan docs | July 24 plan describes an older repository and obsolete providers/sequencing | Supersede as historical evidence |

### 3.3 PR #289 disposition

PR #289 should not be treated as proof that the architecture is complete.

Retain:

- explicit plan → renderer boundary;
- validated reference resolution;
- plan preview;
- provenance intent;
- provider-health transparency.

Amend after merge:

- support a list of characters and reference roles;
- record protected regions and allowed changes;
- record content lane and adult classification;
- record speed/quality mode, budget, attempt ceiling, and privacy;
- compile through a versioned model adapter instead of generic prompt concatenation.

Do not expand PR #289 further before its existing CI failures are repaired. This plan belongs in follow-on packets.

---

## 4. Model and provider decision

Generic leaderboards are discovery tools, not Kitty acceptance evidence. As of July 10, 2026, Arena’s broad text-to-image ranking places GPT Image 2 first. The same leaderboard places Qwen-Image-2512 below several proprietary systems overall, while Qwen remains a leading Apache-2.0 open model. Those rankings do not measure James identity, male body-hair realism, explicit anatomy, regional preservation, or multi-character adult scenes.

### 4.1 Shortlist by role

#### GPT Image 2

**VERIFIED**

- OpenAI’s current state-of-the-art API image generation and editing model.
- Supports high-fidelity image inputs and flexible output sizes.
- Leads the current broad Arena preference table.

**Use in Kitty**

- Safe premium-final benchmark leader.
- Safe complex edit and typography candidate.
- Not a dependable explicit route: service behavior and policy enforcement may reject the workflow, and Kitty must not architect explicit availability around an external moderation assumption.

#### Gemini 3.1 Flash Image / Gemini 3 Pro Image

**VERIFIED**

- Flash is the all-around price/latency model.
- Pro is intended for professional assets and complex instructions.
- Gemini 3 image models support several character references and multi-turn editing.
- Google’s prohibited-use policy bans pornography or sexual-gratification content.

**Use in Kitty**

- Flash: safe draft, composition, and fast multi-reference exploration.
- Pro: safe complex-final challenger and typography.
- Never dispatch explicit adult jobs to Google.

#### FLUX.2

**VERIFIED**

- FLUX.2 max is BFL’s highest-quality final model.
- FLUX.2 pro is the production balance; flex exposes more controls; klein is the fast tier.
- API editing supports multiple references.
- Current API pricing starts around $0.014 for klein, $0.03 for pro generation, and $0.07 for max.
- BFL’s current API terms prohibit pornographic/objectionable content even though the newer usage-policy wording focuses on unlawful and non-consensual content.

**Use in Kitty**

- Safe benchmark challenger, especially multi-reference editing.
- Do not make it the adult route.
- Do not retain FLUX.1 Kontext as the strategic default merely because older research selected it.

#### Qwen-Image-2512 and Qwen-Image-Edit-2511

**VERIFIED**

- Apache-2.0 open weights.
- 2512 focuses on more realistic humans, richer facial details, and natural textures.
- Edit-2511 supports multiple inputs and reports improved character and multi-person consistency.
- Official ecosystem support includes Diffusers and several inference engines; ComfyUI support exists in the ecosystem.

**Use in Kitty**

- Primary open-weight generation/editing family for the first James benchmark.
- Train a James identity LoRA against 2512 or a compatible derivative.
- Use Edit-2511 for regional and multi-person repair.
- Treat community adult LoRAs/checkpoints as benchmark candidates, not truth. Many public samples are female-centric and do not prove male anatomy, body hair, or gay multi-character quality.

#### Qwen-Image 2.0 hosted models

**VERIFIED**

- Current hosted Qwen-Image 2.0 and Pro endpoints exist, while the older 2512/2511 weights are the verified open family in the official repository.
- Broad leaderboard performance is competitive but not the overall leader.

**Use in Kitty**

- Safe benchmark challenger.
- Do not wait for uncertain future weight releases to build the first open lane.

#### Other providers and models

Reve, Seedream, Ideogram, Recraft, Hunyuan, HiDream, Krea, Stability, and other current systems belong in the benchmark intake, not the initial integration set. Kitty should resist provider collection. A candidate earns integration only when it wins a Kitty task category by enough margin to justify another adapter and operational surface.

### 4.2 Initial provider count

Implement exactly three execution adapters first:

1. `hosted_google_image` — safe draft and challenger;
2. `hosted_openai_image` — safe premium final/edit challenger;
3. `open_worker` — Qwen/ComfyUI on Kitty-controlled GPU.

Add BFL as the fourth adapter only if KittyBench demonstrates a material win in safe editing or photorealism. Avoid integrating ten providers before one end-to-end workflow is reliable.

---

## 5. Character Pack design

The existing character row is a useful root object but is not sufficient for high-fidelity recurrent generation.

### 5.1 Character Pack contents

Extend the character domain with:

- canonical fictional-adult assertion and age range;
- immutable character ID and versioned appearance profile;
- 15–30 curated references, while retaining an active subset per model limit;
- “golden” references;
- reference roles: face-front, face-three-quarter, face-profile, expression, full-body, body-detail, hair, beard, body-hair, pose, outfit, lighting, scene, negative-example;
- reference quality: sharpness, occlusion, expression extremity, crop, lighting, face detectability, body visibility;
- stable physical traits and anti-drift constraints;
- model-specific identity profiles;
- LoRA artifacts, trigger tokens, compatible base, training dataset hash, training parameters, and license;
- successful seeds, workflows, adapter versions, and scene categories;
- accepted gallery outputs and rejected failure examples;
- privacy and retention policy.

The active model adapter selects the best subset; the user should not manually reorder twenty images for every attempt.

### 5.2 James identity method

Use layered identity control:

1. **James LoRA** for persistent identity across poses and scenes.
2. **Multiple current-session references** to anchor the requested angle, expression, and body.
3. **Pose/layout control** for scene geometry.
4. **Per-character region assignment** in multi-character scenes.
5. **Face embedding similarity** as advisory evidence.
6. **Localized face or body repair** when the base composition succeeds but identity drifts.

Do not depend on face swap as the default. It can create pasted-on lighting, boundary, age, and expression artifacts and does not solve body or multi-character consistency.

---

## 6. Request lifecycle

```text
natural request
    ↓
ImageIntentContract
    ↓
character/reference resolver
    ↓
content-lane + policy gate
    ↓
session budget reservation
    ↓
model-specific plan compiler
    ↓
draft attempt(s)
    ↓
user or controller selects composition
    ↓
premium final attempt
    ↓
visual critic + deterministic checks
    ↓
accept ── or ── localized repair / bounded regenerate / model switch
    ↓
artifact verification
    ↓
cost reconciliation + session memory + provenance
```

### 6.1 ImageIntentContract

Replace the flat “refined prompt” idea with a structured contract:

```python
@dataclass(frozen=True)
class ImageIntentContract:
    schema_version: int
    user_goal: str
    subjects: list[SubjectIntent]
    scene: str
    composition: CompositionIntent
    camera: CameraIntent
    lighting: LightingIntent
    mood: str | None
    realism: RealismIntent
    protected_regions: list[ProtectedRegion]
    allowed_changes: list[str]
    references: list[ReferenceRole]
    exact_text: list[str]
    negative_constraints: list[str]
    content_lane: Literal["safe", "fictional_adult_explicit"]
    fictional_adults_verified: bool
    aspect_ratio: str
    target_resolution: str
    quality_mode: Literal["draft", "final", "repair"]
    maximum_cost_usd: Decimal
    maximum_attempts: int
    privacy_level: Literal["private", "local_only", "provider_allowed"]
```

The contract is provider-neutral. It contains user intent, not sampler settings.

### 6.2 Model adapters

Each adapter is versioned and owns:

- prompt style;
- reference ordering and limits;
- negative prompt behavior;
- mask encoding;
- seed and determinism behavior;
- aspect/resolution constraints;
- LoRA triggers and strengths;
- step/CFG/sampler defaults for open models;
- provider request and progress mapping;
- cost estimator;
- policy capabilities;
- output/provenance parser.

Example IDs:

- `gemini-3.1-flash-image@1`
- `gpt-image-2@1`
- `qwen-image-2512-james-final@1`
- `qwen-image-edit-2511-regional@1`

A recipe must point to a real adapter and a validated workflow hash. A database row without an executable adapter is unavailable.

---

## 7. Session, attempts, state, and data

Retain `image_jobs` as the dispatch record. Add domain records around it.

### 7.1 New tables

- `image_sessions` — user goal, active characters, contract version, selected attempt, budget reserved/incurred, status.
- `image_attempts` — session, job, stage, parent attempt, adapter version, seed, intent hash, outcome.
- `image_stage_events` — queued/loading/generating/downloading/evaluating/repairing, timestamps, provider progress, ETA range.
- `image_critiques` — structured scores, visible defects, confidence, critic model/version.
- `image_repairs` — source artifact, mask, protected-region hash, requested change, result.
- `image_artifacts` — original/final/thumbnail/mask/critic-overlay, checksum, dimensions, storage policy, provenance.
- `character_reference_roles` — character/ref/role/quality/active status.
- `character_model_profiles` — character, adapter, LoRA, preferred refs, weights, successful settings, benchmark version.
- `image_cost_ledger` — reservation, estimated cost, provider-reported usage, reconciled cost, currency/source date.

### 7.2 State machine

```text
planning
  → awaiting_approval
  → budget_reserved
  → queued
  → preprocessing
  → generating
  → retrieving
  → evaluating
  → accepted
  → repairing → evaluating
  → retrying → queued
  → failed
  → canceled
  → budget_exhausted
```

`image_jobs` remains the provider dispatch state. `image_sessions` describes the multi-attempt user workflow. This avoids forcing an entire session into one job row while preserving one canonical execution ledger.

---

## 8. Generate–evaluate–repair controller

Automatic iteration must be bounded and legible.

### Defaults

- Draft attempts: maximum 4 without user interaction.
- Premium final attempts: maximum 2.
- Automatic repairs: maximum 2.
- Total automatic provider calls: maximum 8.
- Default safe-session budget: $1.25.
- Default open-worker session reservation: $1.50.
- Hard per-session ceiling: $3.00 unless explicitly raised.
- No automatic credit refill.
- No automatic persistent worker.

These are initial guardrails, not proven optimums.

### Critic output

```json
{
  "identity": [{"character_id": "char_...", "score": 0.0, "confidence": 0.0}],
  "prompt_adherence": 0.0,
  "photorealism": 0.0,
  "anatomy": 0.0,
  "skin_texture": 0.0,
  "hair_texture": 0.0,
  "lighting_consistency": 0.0,
  "composition": 0.0,
  "protected_region_preservation": 0.0,
  "text_accuracy": 0.0,
  "visible_defects": [],
  "recommended_action": "accept|repair|regenerate|switch_model|ask_user|stop",
  "reason": "",
  "confidence": 0.0
}
```

### Deterministic evidence

Use model criticism alongside:

- ArcFace-compatible identity similarity on detected faces;
- protected-region SSIM/LPIPS and perceptual-feature difference;
- face count and face-to-character assignment;
- OCR exact match;
- mask boundary checks;
- image checksum and duplicate/perceptual-hash detection;
- duration and cost.

Automated identity scores are advisory. They can be fooled by angle, expression, lighting, and overfitted face structure. A human decision remains required before a result becomes a “golden” character reference.

### Plateau detection

Stop when any is true:

- two attempts differ little perceptually but fail the same high-priority criterion;
- best weighted score improves by less than 2 percentage points across two calls;
- identity improves while protected-region damage worsens beyond threshold;
- budget or attempt ceiling is reached;
- critic confidence is low and the next action would be destructive;
- the same normalized defect occurs three times.

---

## 9. Multi-character scenes

One-pass prompting is not an adequate architecture.

Use:

1. composition/layout draft without strict final identity;
2. assign each subject a character ID, reference subset, and spatial region;
3. render with per-character conditioning;
4. detect and associate faces;
5. repair each character independently;
6. repair interactions, hands, and occlusion;
7. run final global lighting/texture check without changing protected faces.

The contract must reject ambiguous reference ownership. Every face/body/outfit reference belongs to one character or to the scene.

For the first release, support two recurring characters. Expand only after the two-character benchmark is reliable.

---

## 10. Progress and ETA

Never convert elapsed time into a fake percentage.

### Before dispatch

Show:

- selected lane, provider, model, and adapter version;
- queue/cold-start expectation;
- estimated preprocessing, generation, retrieval, critique, and repair ranges;
- estimated total range and confidence;
- estimated maximum cost;
- attempt ceiling and automatic-repair setting.

### During dispatch

Normalized stages:

- `queued`
- `worker_starting`
- `model_loading`
- `preprocessing`
- `generating`
- `retrieving`
- `evaluating`
- `repairing`
- `finalizing`

Use provider progress only when genuine. Otherwise estimate from Kitty history by:

`provider × adapter version × GPU/model × operation × resolution × cold/warm state`.

Store rolling p50/p80/p95 durations. Display ranges such as “about 45–90 seconds,” not “63 seconds remaining” when no step telemetry exists.

For ComfyUI, websocket/node progress may enrich the `generating` stage. For hosted APIs with only job status, display stage-level progress.

---

## 11. Reliability and cost controls

- Idempotency key = hash of session, attempt, intent contract, adapter version, and explicit retry nonce.
- Reserve maximum attempt cost before provider dispatch.
- Reconcile against provider usage or measured GPU runtime.
- Separate retryable errors: queue timeout, worker loss, provider 5xx, transient download failure.
- Terminal errors: policy rejection, invalid adapter, missing model/node, corrupt reference, budget refusal.
- Persist provider request ID before polling.
- Accept webhook events idempotently; poll when webhooks are delayed or lost.
- Verify artifact bytes before `SUCCEEDED`.
- Recover partial outputs where the provider completed but callback/download failed.
- Cancel queued and active work through provider-specific cancellation.
- Set RunPod `workersMin=0`, `workersMax=1` initially, short idle timeout, and hard execution timeout.
- Allow GPU fallback categories only when memory and cost ceilings are compatible.
- Shut down/scale to zero automatically.
- Apply daily and monthly caps, not just per-session limits.

---

## 12. Benchmark

### 12.1 Kitty Character Image Bench

Use private reference sets and fictional adults only.

Core tasks:

1. James neutral headshot from one reference.
2. James from several references and a new angle.
3. James full-body realism.
4. Body-only edit with face protected.
5. Eye-color correction with identity protected.
6. Beard, head hair, and body-hair realism.
7. Lighting change with face and body protected.
8. Clothing replacement.
9. Background replacement.
10. Pose transfer.
11. James across four scenes.
12. James plus one second recurring character.
13. Two characters interacting with correct identity assignment.
14. Hands and occlusion.
15. Localized face repair.
16. Localized body/anatomy repair.
17. Long natural-language instruction.
18. Short natural request requiring plan inference.
19. Exact text rendering.
20. Fictional-adult explicit photorealism and safety-negative cases.

### 12.2 Measures

- blind Jacob preference;
- identity similarity;
- prompt adherence;
- protected-region preservation;
- photorealism and texture;
- anatomy;
- multi-character assignment;
- failure/refusal rate;
- latency p50/p95;
- raw cost;
- successful-result cost;
- number of repair calls;
- critic/human agreement.

Do not publish explicit benchmark artifacts. Retain encrypted/private metadata and aggregate scores.

### 12.3 Promotion rule

A new adapter becomes a default only when:

- it beats the current default on the relevant Kitty category;
- the difference is larger than normal run-to-run variance;
- cost/reliability remain acceptable;
- licensing and policy are current;
- the win reproduces on a held-out prompt set.

---

## 13. Cost model

All figures below are **USD, before tax, storage growth, and foreign-exchange effects**.

### 13.1 Defined session

A normal character session is:

- one intent-plan pass;
- up to six draft images;
- two premium-final attempts;
- one localized repair;
- critique of viable attempts;
- artifact storage and provenance.

A successful session may stop earlier.

### 13.2 Verified unit anchors

- Gemini 3.1 Flash Image: about $0.067 per 1K output, $0.101 at 2K, and $0.151 at 4K.
- Gemini 3 Pro Image: about $0.134 at 1K/2K and $0.24 at 4K, plus input.
- FLUX.2 pro generation: from $0.03; max: from $0.07; pricing grows with megapixels.
- RunPod Serverless Flex currently lists about $1.10/hour for a 24 GB 4090 tier, $1.22/hour for a 48 GB A6000/A40 tier, $1.75/hour for a 48 GB L40/L40S tier, and $2.72/hour for A100 80 GB.
- Modal lists L40S at $0.000542/second and A100 80 GB at $0.000694/second.

### 13.3 Session envelopes

These are **HYPOTHESES pending Kitty timing measurements**:

| Workflow | Estimated successful-session envelope | Main uncertainty |
|---|---:|---|
| Safe hosted | $0.60–$1.10 | final quality/resolution and number of edits |
| Open fictional-adult | $0.35–$1.35 after LoRA setup | cold start, Qwen quantization, steps, repair count |
| Premium “best available” comparison session | $1.25–$3.00 | racing several final models |

At the open-worker midpoint of roughly $0.80/session, deposits last approximately:

| Deposit | Expected sessions | Conservative range |
|---:|---:|---:|
| $10 | 12 | 7–28 |
| $20 | 25 | 15–57 |
| $50 | 62 | 37–143 |
| $100 | 125 | 74–286 |

The range excludes one-time LoRA training and assumes automatic ceilings prevent runaway retries.

### 13.4 Monthly envelopes

| Sessions/month | Safe hosted | Open fictional-adult |
|---:|---:|---:|
| 25 | $15–$28 | $9–$34 |
| 100 | $60–$110 | $35–$135 |
| 500 | $300–$550 | $175–$675 |
| 2,000 | $1,200–$2,200 | $700–$2,700 |

At 500–2,000 sessions, re-evaluate warm workers, batching, optimized inference engines, and direct model serving. The recommended personal-use starting point remains scale-to-zero.

### 13.5 First-month budget

Recommended cap: **$50 USD**, no auto-refill.

- $10 — hosted draft/final benchmark.
- $10 — open-worker cold-start and hardware benchmark.
- $10 — James LoRA training and one retraining allowance.
- $15 — ordinary character sessions.
- $5 — storage, critic, and failure reserve.

Expected outcome: one validated James profile and approximately 20–50 successful sessions, depending on training retries and final quality targets. Increase the cap only after Kitty records actual successful-result cost.

---

## 14. Implementation roadmap

This is a later-phase plan. It does not bypass Phase 1 in `docs/ROADMAP.md`.

### IMG-CF-00 — Truthful disposition and benchmark harness

**Objective:** Remove false readiness and establish the baseline.

**Areas:** `gateway/image_recipes.py`, `gateway/image_runner.py`, `gateway/image_gen.py`, `tests/test_image_*`, `docs/plans/`

**Deliverables**

- mark every non-operational recipe unavailable;
- capability probe that verifies model, node, adapter, and workflow compatibility;
- baseline character benchmark runner and private result format;
- freeze current output examples and costs where available.

**Acceptance**

- UI cannot select a recipe that cannot execute;
- baseline tests demonstrate current single-reference limitation;
- benchmark produces a reproducible JSON result.

**Delegation:** KittyBuilder can implement; specialist judgment chooses benchmark prompts and ratings.

### IMG-CF-01 — Intent Contract and ImagePlan v2

**Objective:** Deepen PR #289’s plan boundary without generating images.

**Areas:** `gateway/image_plan.py`, new `gateway/image_intent.py`, Studio routes, plan preview UI.

**Deliverables**

- versioned contract;
- multiple subjects and reference roles;
- protected regions and allowed changes;
- content lane, privacy, budget, and attempt ceiling;
- validation and serialization.

**Acceptance**

- same input produces deterministic validated contract;
- ambiguous reference ownership fails;
- explicit lane requires fictional-adult assertion;
- plan preview displays the material decisions.

**Delegation:** KittyBuilder after architecture review.

### IMG-CF-02 — Executable adapter registry

**Objective:** Replace optimistic recipe claims with runnable adapters.

**Areas:** new `gateway/image_adapters/`, `gateway/image_recipes.py`, `gateway/image_runner.py`.

**Deliverables**

- adapter protocol;
- versioned capabilities;
- health/cost/policy metadata;
- Google, OpenAI, and open-worker skeletons;
- recipe → adapter binding.

**Acceptance**

- adapter health proves executable readiness;
- no route calls provider SDK directly;
- model-specific prompt compilation has golden tests.

**Delegation:** KittyBuilder; provider-policy mapping needs direct review.

### IMG-CF-03 — Session and attempt persistence

**Objective:** Represent the whole iterative workflow without replacing `image_jobs`.

**Areas:** migrations, `gateway/image_jobs.py`, new `image_sessions.py`, `image_attempts.py`.

**Deliverables**

- tables listed in §7;
- transactional attempt creation;
- artifact and cost lineage;
- restart reconciliation.

**Acceptance**

- crash after provider submission resumes safely;
- session reconstructs selected refs, attempts, spend, and accepted artifact;
- duplicate callbacks are idempotent.

**Delegation:** KittyBuilder.

### IMG-CF-04 — Character Pack v3

**Objective:** Turn references into an effective identity asset.

**Areas:** `gateway/image_characters.py`, migrations, upload routes, Studio character UI.

**Deliverables**

- reference roles and quality;
- active/model-specific reference sets;
- golden references;
- model profiles and LoRA artifacts;
- versioned appearance constraints.

**Acceptance**

- at least 15 references can be stored while adapters enforce their own limits;
- every reference has ownership and role;
- a model profile resolves a deterministic subset.

**Delegation:** KittyBuilder; Jacob curates the James references.

### IMG-CF-05 — Open-worker Qwen lane

**Objective:** Produce a durable safe and fictional-adult-capable open-weight path.

**Areas:** deployment container, ComfyUI workflows, open-worker adapter, secrets/config, health checks.

**Deliverables**

- Qwen-Image-2512 generation;
- Qwen-Image-Edit-2511 editing;
- Qwen3-VL critic candidate;
- RunPod Flex deployment with zero minimum workers;
- cancellation, timeout, and artifact upload.

**Acceptance**

- no idle worker remains after timeout;
- explicit jobs never leave the open lane;
- cold/warm duration and cost are recorded;
- missing model/node fails before spend.

**Delegation:** Specialist-led initial workflow; KittyBuilder can harden afterward.

### IMG-CF-06 — James LoRA training and profile

**Objective:** Establish the persistent fictional character identity.

**Areas:** private dataset tooling, training manifest, artifact store, Character Pack UI.

**Deliverables**

- curated dataset manifest;
- training/evaluation split;
- versioned LoRA;
- trigger token and compatible-base metadata;
- benchmark comparison against reference-only control.

**Acceptance**

- held-out tasks improve identity without unacceptable pose/expression collapse;
- artifact can be rolled back;
- no training image is silently added from generated outputs.

**Delegation:** Human curation and specialist judgment required.

### IMG-CF-07 — Draft → final promotion

**Objective:** Make cheap exploration and premium finals explicit.

**Areas:** Studio session UI, router, cost estimator, attempt controller.

**Deliverables**

- draft mode;
- select/promote composition;
- final adapter choice;
- side-by-side final race option;
- cost reservation.

**Acceptance**

- draft model is never silently reused as final when premium mode is selected;
- user sees estimated maximum spend;
- selected composition and seed/context remain linked.

**Delegation:** KittyBuilder.

### IMG-CF-08 — Localized repair

**Objective:** Fix defects without destroying accepted regions.

**Areas:** mask UI, edit adapter, artifact lineage, critique/controller.

**Deliverables**

- user and critic masks;
- protected-region hashes;
- face/body/hands/background repair presets;
- Qwen Edit workflow;
- safe hosted edit challenger.

**Acceptance**

- body-only benchmark preserves protected face above threshold;
- each repair links source, mask, instruction, and result;
- repair can be rejected without losing source artifact.

**Delegation:** Mixed; mask/UI to KittyBuilder, workflow tuning specialist-led.

### IMG-CF-09 — Multi-character v1

**Objective:** Reliably support two recurring characters.

**Areas:** intent schema, composition controls, adapter compiler, critic association.

**Deliverables**

- per-character regions and refs;
- two-character composition workflow;
- face/character assignment;
- independent repair.

**Acceptance**

- held-out two-character tasks preserve both identities;
- swapped identities are detected;
- one character can be repaired without materially changing the other.

**Delegation:** Specialist design, KittyBuilder implementation.

### IMG-CF-10 — Critique and bounded repair controller

**Objective:** Add evidence-driven iteration without runaway spend.

**Areas:** `image_quality.py`, critic adapter, deterministic metrics, controller.

**Deliverables**

- structured critique;
- plateau detection;
- accept/repair/regenerate/switch/stop policy;
- user override;
- critic-human agreement tracking.

**Acceptance**

- hard attempt and spending ceilings cannot be bypassed;
- near-duplicate loops stop;
- critic recommendations are auditable;
- explicit images use local critic.

**Delegation:** Specialist judgment plus KittyBuilder.

### IMG-CF-11 — Honest ETA and progress

**Objective:** Display useful uncertainty rather than fabricated precision.

**Areas:** stage events, provider adapters, duration statistics, Studio progress UI.

**Deliverables**

- normalized stages;
- rolling p50/p80/p95;
- queue/cold-start split;
- real provider progress mapping;
- cost incurred.

**Acceptance**

- UI labels modeled versus provider-reported progress;
- ETA narrows as stages complete;
- no exact countdown appears without sufficient evidence.

**Delegation:** KittyBuilder.

### IMG-CF-12 — Default selection and release gate

**Objective:** Promote defaults only from Kitty evidence.

**Deliverables**

- full benchmark report;
- selected draft/final/edit/critic adapters;
- monthly cap recommendation;
- failure and policy review;
- browser/runtime proof.

**Acceptance**

- defaults map to benchmark version;
- provider terms and pricing dates are recorded;
- one complete James session survives restart and repair;
- one two-character session completes;
- cost ledger reconciles.

**Delegation:** Direct specialist and Jacob judgment.

---

## 15. Migration

1. Merge and repair PR #289 independently; do not mix this roadmap into its 129-commit sweep.
2. Preserve all current character IDs, references, gallery rows, jobs, and artifacts.
3. Add tables and nullable foreign keys; do not rewrite old jobs.
4. Create a legacy adapter descriptor for historical ComfyUI outputs.
5. Mark optimistic recipes unavailable rather than deleting them immediately.
6. Migrate primary refs into role `face_primary`; preserve original ordering.
7. Introduce sessions only for new work; optionally backfill one session per historical job.
8. Keep `image_runner` as the single dispatch boundary.
9. Introduce direct hosted adapters behind the runner, not separate routes.
10. Supersede old plans with pointers; retain them as evidence.

---

## 16. Risk register

| Risk | Control |
|---|---|
| Identity drift | LoRA + multiple references + per-character repair + human golden approval |
| False “100% likeness” promise | measurable thresholds and visible evidence |
| Cost runaway | reservation, attempt ceiling, daily/monthly cap, zero auto-refill |
| Idle GPU billing | scale-to-zero, min workers zero, short idle timeout |
| Cold-start frustration | learned ETA; optional warm worker only after usage proves value |
| Hosted policy changes | dated capability/policy registry and open lane |
| Explicit data leakage | local/open-worker lane, private storage, retention controls |
| Minor/ambiguous-age content | fictional-adult assertion, age checks, hard refusal |
| Real-person deceptive intimate use | provenance, fictional/consent record, deny unsupported identity sources |
| Community checkpoint malware | safetensors-only, hash allowlist, isolated scanning/build |
| License conflict | model/LoRA license recorded and release blocked when unknown |
| Multi-character identity swap | region assignment and critic face-to-character matching |
| Overfitted James LoRA | held-out views/expressions and rollback |
| Critic hallucination | deterministic checks and human comparison |
| Benchmark overfit | held-out tasks and periodic refresh |
| Provider outage | adapter fallback within same content lane |
| Webhook loss | idempotent polling fallback |
| Duplicate spend | idempotency key and reservation transaction |
| Misleading UI | capabilities derived from health, not labels |

---

## 17. Final recommendation

Build the first successful James workflow before broad provider expansion:

1. truthful capability cleanup;
2. ImageIntentContract;
3. session/attempt records around existing jobs;
4. Character Pack reference roles;
5. Qwen open-worker lane;
6. one versioned James LoRA;
7. draft-to-final promotion;
8. localized repair;
9. two-character support;
10. critic, ETA, and default promotion from KittyBench.

The most important correction is strategic:

> Kitty should minimize the cost of discovering the right composition, then maximize the quality of the small number of final renders. The final model is chosen by James benchmark performance, not by raw image price.

---

## 18. Sources reviewed

### Kitty repository

- `gateway/image_jobs.py`
- `gateway/image_characters.py`
- `gateway/image_recipes.py`
- `gateway/image_gen.py`
- `gateway/image_runner.py`
- PR #289 `gateway/image_plan.py`
- `docs/ROADMAP.md`
- `docs/planning/image-studio-character-system-2026-07-24.md`
- `docs/plans/image-runner-and-recipe-cleanup.md`

### Current external sources

- Google Gemini image generation: https://ai.google.dev/gemini-api/docs/image-generation
- Google Gemini pricing: https://ai.google.dev/gemini-api/docs/pricing
- Google Generative AI Prohibited Use Policy: https://policies.google.com/terms/generative-ai/use-policy
- OpenAI GPT Image 2 model: https://developers.openai.com/api/docs/models/gpt-image-2
- OpenAI Usage Policies: https://openai.com/policies/usage-policies/
- Black Forest Labs FLUX.2 overview: https://docs.bfl.ai/flux_2/flux2_overview
- Black Forest Labs pricing: https://docs.bfl.ai/quick_start/pricing
- Black Forest Labs Usage Policy: https://bfl.ai/legal/usage-policy
- Black Forest Labs Terms of Service: https://bfl.ai/legal/terms-of-service
- Qwen Image official repository: https://github.com/QwenLM/Qwen-Image
- Qwen3-VL official repository: https://github.com/QwenLM/Qwen3-VL
- Arena text-to-image leaderboard, 2026-07-10 snapshot: https://arena.ai/leaderboard/text-to-image
- RunPod Serverless pricing: https://docs.runpod.io/serverless/pricing
- RunPod endpoint settings: https://docs.runpod.io/serverless/endpoints/endpoint-configurations
- Modal pricing: https://modal.com/pricing

Source claims and pricing must be rechecked at implementation and again before default promotion.
