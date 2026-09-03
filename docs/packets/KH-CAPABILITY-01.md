# KH-CAPABILITY-01 — Capabilities expose installed/configured/available/launchable truth

**Initiative:** `kitty-hardening-capability-health-20260903-v1`  
**Owner:** Builder after explicit operator activation  
**Default route:** free; no `policy.routing` pin  
**Base authored against:** `origin/main` `70c15583a6afa4aac9a6f6eb11abf840afa377a4`  
**Status:** authored only — not applied, queued, or dispatched

## What Jacob can do after this
Jacob can see whether a Kitty capability is installed, configured, currently available, launchable, or degraded—and why—without the frontend guessing across several endpoints.

## Verified finding
Capability catalog, skills, plugin state, provider health, MCP servers, and runtime health are separate projections. `/capabilities` mostly says what exists/where it launches, while consumers must infer whether it will actually work. The review recommended one read-only capability-health contract rather than another state store.

## Objective
This packet creates no new files. Depend on KH-PLUGIN-01. Extend the existing capability projection, reusing `capability_manifest`, runtime/health/provider/plugin/skill authorities, to expose a small read-only health envelope per capability. Preserve domain truth: distinguish installed, configured, available, launchable, degraded/blocked, and unknown instead of collapsing them into one boolean. Every unavailable/degraded state that can affect a user action carries a safe reason and, when already known by an existing authority, one recovery hint. Do not persist capability health, add a new registry, poll external providers inside the projection, or fabricate health for capabilities without evidence. Adopt the contract in exactly one existing consumer (recommended Capability Launcher/Settings) to prove it can disable or explain an unavailable capability without domain-specific special cases; broad UI migration is follow-up work.

## Intended files / fence
- `gateway/routes/capabilities.py`
- `gateway/capability_manifest.py`
- `gateway/health_surface.py`
- `gateway/plugin_registry.py`
- `tests/test_capabilities_route.py`
- `tests/test_capability_manifest.py`
- `gateway/kitty-chat/src/lib/gateway.ts`
- `gateway/kitty-chat/src/lib/capability-launch.ts`
- `gateway/kitty-chat/tests/capabilityLaunch.test.ts`

This is a deliberate edit-only fence: the executable objective says `creates no new files` If a new module/test becomes necessary, stop and revise the manifest first.

## Acceptance criteria
1. Capability responses distinguish installed/configured/available/launchable/degraded-or-blocked/unknown without inventing a new persisted state machine.
2. An unavailable capability carries a safe reason; UNKNOWN remains unknown rather than false unavailable or healthy.
3. Health is derived from existing authorities and the capability route performs no new network/provider polling itself.
4. One existing frontend consumer renders/blocks from the shared health envelope instead of its own special-case availability guess.
5. Core capability IDs/destinations remain backward compatible for currently launchable features.
6. No new registry, scheduler, database table, or provider configuration authority is introduced.

## Verification
**Tier 1 — Builder mechanical.** These are the only commands Builder runs:
- `python -m pytest -q tests/test_capabilities_route.py tests/test_capability_manifest.py`
- `python -m ruff check gateway/routes/capabilities.py gateway/capability_manifest.py gateway/health_surface.py gateway/plugin_registry.py tests/test_capabilities_route.py tests/test_capability_manifest.py`

**Tier 2 / Tier 3.** Tier 2: frontend capability-launch tests plus a running-app unavailable/recovery state at desktop and iPhone width. Tier 3: independent reviewer opens one available and one unavailable capability and confirms the displayed reason/action matches backend truth.

Current-green tests are baseline only. The implementation must add or strengthen at least one regression that fails on `70c15583a6afa4aac9a6f6eb11abf840afa377a4` for the verified finding before production edits.

## Failure modes that must be tested
- The original review reproduction is a required RED case, not prose-only evidence.
- Dependency/service unavailable paths stay truthful; UNKNOWN never becomes success.
- Cancellation/timeout/partial input cannot leave a false success receipt.
- The fix must preserve the existing security/authority boundary named in the objective.

## Stop condition
If a capability can only be classified by actively invoking a paid/external provider, leave it UNKNOWN and stop that adapter; capability projection is read-only.

## Recovery / restartability
Read-only projection over existing authorities; no migration or durable health state.

## Dedupe / ownership guard
Before activation, re-read `workspace_global`, GitHub issue #490, current Git/PR state, and Builder task ownership. If current `main` already contains an equivalent fix or another live lane owns any implementation path, stop and reconcile rather than creating competing work. This packet never authorizes push, PR creation, merge, paid spend, credential mutation, or edits under `data/`.
