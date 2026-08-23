# ImageBench Current Baseline Evidence — 2026-08-23

**Evidence status:** research / current-state packet, not a promotion decision.  
**Current main inspected:** `409c73320e7a132d7c27ec3229316d404a62fa00` (PR #605 merged).  
**Live runtime build observed:** `cd1e4d692706c71cbbdfcf44d3ea70b63d20c0ae`.  
**Machine-readable companion:** `imagebench-current-baseline-2026-08-23.json`.

## Executive result

There is **no valid current ImageBench baseline yet**. That is a measured result, not an absence of work. Current main now has versioned ImageIntent provenance, a fail-closed evaluation contract, and the offline ImageBench runner, but the live Kitty process is older than current main and the evidence needed for a quality/economics comparison is incomplete.

The live Image Lab readiness surface currently selects **fal** as the available backend. fal is available; Airforce is blocked by a $0 balance; ComfyUI and Draw Things are offline; legacy BFL Flux and OpenRouter are disabled by the paid switch. No provider generation was performed while producing this packet.

## Authority split

| Evidence | Observed truth |
|---|---|
| Current repository | `origin/main` = `409c73320e7a132d7c27ec3229316d404a62fa00` |
| Live gateway build | `cd1e4d692706c71cbbdfcf44d3ea70b63d20c0ae` |
| Runtime manifest revision | `d326be95037a1c1c` |
| Live selected image backend | `fal` |
| Canonical local worktree | intentionally not used as current-code authority; it is behind `origin/main` and has an unrelated local config change |

The runtime/readiness facts below describe the live process at its observed build, not a launch proof for current main.

## Live route readiness

| Engine | Available | Current reason / price evidence |
|---|---:|---|
| ComfyUI | false | ComfyUI is not running on this Mac. Start ComfyUI, then check again. |
| Draw Things | false | Draw Things is not answering. Open the Draw Things app, turn on its API server, then check again. |
| Airforce | false | Airforce account balance is $0. Add pay-as-you-go credits before using hosted image generation. |
| fal / FLUX PuLID | true | status advertises $0.0333/output MP and $0.0666 for the default square output |
| legacy BFL Flux | false | Paid image generation is off. Flux image generation is billed per request. Set KITTY_IMAGE_PAID_ENABLED=1 in .env and restart Kitty to turn it on. |
| OpenRouter image | false | Paid image generation is off. OpenRouter image generation is billed usage. Set KITTY_IMAGE_PAID_ENABLED=1 in .env and restart Kitty to turn it on. |

The effective non-secret `.env` configuration sets `FAL_MODEL=fal-ai/flux-pulid` and `AIRFORCE_MODEL=image-1-watermark`, with both provider-specific enable switches on. This exposes an Airforce configuration drift: current-main recipe/status text describes Grok Imagine Image 2.0, while the effective model setting is `image-1-watermark`. Airforce health stops earlier because the account balance is $0, so the effective model is not currently a runnable benchmark candidate.

## Existing durable output evidence

The runtime DB contains two successful historical image jobs. Neither qualifies as an ImageBench baseline.

### Recent fal success

- Job: `job_d6f3e1e517c94e3fafde8dab99d73e87`
- Model: `fal-ai/flux-pulid`
- Measured job runtime: `8.461448` seconds
- Canonical Artifact SHA-256: `f4aa28e934ba0ad60a6d3dac0a5f6a22c64b0f802e7c5430d6450ad2941917f4`
- Session spend field: `$0.07`

This output is useful historical evidence, but **not admissible for current ImageBench comparison**:

1. The live `image_jobs` schema has no `plan_id` or `intent_json` columns yet, because the runtime predates the merged ImageIntent provenance work.
2. The runtime DB has `0` image plan rows and `0` image-job observation rows.
3. There are `0` rated gallery items, so no blind keeper/accepted decision exists.
4. No required ImageBench scorer evidence/version set exists.
5. `$0.07` is the session budget reservation. Current main's fal registry-hosted runner returns `JobResult.cost_usd=None`, so that value is not reconciled into provider-reported settled cost and must not be used as cost-per-accepted-image evidence.
6. Artifact metadata has no width, height, seed, workflow template/hash, or compiler version for this historical job.

The older OpenRouter success predates canonical Image Artifact linkage and the current provenance contract even further, so it is also non-qualifying.

## Current candidate disposition

The companion JSON records eight current route candidates. Every candidate is `imagebench_ready=false` today. Important dispositions:

- **fal PuLID:** live and usable, but blocked for benchmark promotion by stale live runtime, missing settled-cost propagation, missing production scorers, and no keeper ratings.
- **Airforce:** blocked by $0 account balance plus effective-model drift (`image-1-watermark` vs the Grok recipe/status contract).
- **ComfyUI / RealCoreXL:** offline; checkpoint filename is known but the model file/hash is not currently discoverable, so exact model provenance is incomplete.
- **Draw Things:** offline; current main records `drawthings@<URL>` as `image_jobs.model_id` rather than the actual `DT_MODEL` (`icatcher_realistic` by default), which is insufficient reproducibility provenance.
- **FLUX.2 Klein 4B / Pro:** current main has exact target IDs and `flux2@1` compiler semantics, but the paid lane is off and there are no ImageBench outputs/scorer/keeper results.
- **Legacy BFL Flux / OpenRouter:** retained as current compatibility routes, but disabled and not benchmark-qualified.

## Concrete code/evidence blockers

### B1 — production scorers are absent

`gateway/image_evaluation.py` correctly fails closed, but no production scorer registry currently supplies the ImageBench names. The legacy `mcp/imagen` code contains reusable mechanics and InsightFace pieces; its vision-rubric path returns a neutral `0.5` when unavailable, so that legacy path **must not** be connected directly to ImageBench without a fail-closed adapter.

### B2 — fal/Airforce settled cost is not propagated

`gateway.image_runner._run_registry_hosted()` returns no `cost_usd`. `studio_generate()` therefore retains the conservative reservation instead of reconciling actual cost. ImageBench intentionally rejects a budget reservation as settled-cost evidence.

### B3 — Draw Things model identity is not durable

The Draw Things engine sends `DT_MODEL` to the local API, but its `model_name`/job provenance identifies only the endpoint. A benchmark job cannot prove which model actually rendered it.

### B4 — current main is not the live runtime

The live gateway is `cd1e4d692706c71cbbdfcf44d3ea70b63d20c0ae`. Restarting/reconciling Kitty onto current main is required before any new output can prove the merged ImageIntent/ImageBench path.

## Next bounded action

Do **not** spend on a challenger yet. The next highest-information engineering slice is:

1. add fail-closed, versioned canonical scorer adapters for the locally provable mechanics/identity checks;
2. fix durable model/cost provenance for the current production routes (especially fal/Airforce settled cost and Draw Things actual model identity);
3. launch current main and verify migrations/runtime revision;
4. only then run the smallest current-route baseline set, collect blind keeper ratings, and let ImageBench report keep rate/cost/latency.

Until those conditions are met, any numeric "winner" or keep-rate would be invented evidence and must not be recorded as a baseline.
