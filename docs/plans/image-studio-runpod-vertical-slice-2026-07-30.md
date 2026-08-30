# Image Studio RunPod Vertical Slice

**Status:** Jacob-authorized implementation input
**Authorized:** 2026-07-30
**Scope:** Bounded RunPod-first smoke loop using Kitty's existing image subsystem

## Objective

Prove one reliable, cost-bounded loop:

> prompt → provision or connect to RunPod → authenticated worker health → submit one frozen ComfyUI workflow → download image and provenance → record estimated cost → terminate compute

## Constraints

- Preserve existing `image_jobs`, gallery, runner, provider, and storage foundations.
- Do not create a second image orchestrator or duplicate job state machine.
- No paid execution until the RunPod API key and explicit live-test approval are provided locally.
- No automatic retry after an ambiguous billable submission.
- Raw ComfyUI and ComfyUI Manager must not be exposed publicly.
- Default session budget: $2.00.
- Default idle timeout: 10 minutes.
- Default hard runtime: 120 minutes.
- Permanent outputs live locally; RunPod storage is model/cache/transfer storage.

## First deliverable

Add a standalone `scripts/runpod_smoke_test.py` that can connect to a configured Kitty worker, submit `text_to_image_v1`, download outputs and provenance, estimate cost, and terminate a Kitty-managed Pod in a `finally` path. Pod creation support must use the current official RunPod control API and remain disabled until required configuration is present.

## Acceptance

1. Missing configuration fails loudly without printing secrets.
2. Existing-Pod development mode works without provisioning.
3. Created Kitty-managed Pods are terminated unless an explicit dangerous keep-alive pair of flags is supplied.
4. Ambiguous post-submission timeouts are reported and never retried automatically.
5. Output image and provenance JSON are saved together.
6. Narrow tests cover configuration, cost estimation, state handling, and cleanup behavior.

## Deferred

Airforce, Draw Things, OpenAI, Google, OAuth, identity workflows, masking, reference tray, model benchmarking, and advanced version UI.
