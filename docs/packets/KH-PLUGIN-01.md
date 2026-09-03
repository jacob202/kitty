# KH-PLUGIN-01 — The plugin surface is either populated by real definitions or truthfully unavailable

**Initiative:** `kitty-hardening-plugin-bootstrap-20260903-v1`  
**Owner:** Builder after explicit operator activation  
**Default route:** free; no `policy.routing` pin  
**Base authored against:** `origin/main` `70c15583a6afa4aac9a6f6eb11abf840afa377a4`  
**Status:** authored only — not applied, queued, or dispatched

## What Jacob can do after this
Jacob can open Kitty's plugin/integration surface and see real registered capabilities with truthful availability instead of an always-empty abstraction.

## Verified finding
`gateway/plugin_registry.py` implements registration, enable/disable persistence, hooks, skills, and MCP aggregation, but no production caller discovered during review registers definitions. Live `/plugins` and `/mcp/servers` both returned empty while tests only register synthetic plugins.

## Objective
This packet creates no new files. Make the existing plugin abstraction honest without introducing arbitrary code loading or a second capability registry. First inventory current built-in integrations/skills/MCP definitions and confirm whether any already satisfy the plugin contract. If real plugin definitions exist conceptually, add one explicit idempotent startup/bootstrap function in the existing plugin registry/integration startup path that registers only trusted built-ins through the existing `plugin_registry.register()` API and is idempotent across reloads/tests. Availability failures must remain visible as `available:false`/reason rather than silently removing the plugin. If no current built-in maps cleanly to plugins, do not invent fake plugins: instead make `/plugins` return an explicit supported/empty-state contract and hide/label plugin controls as not configured. Do not add filesystem code discovery, `importlib` execution of third-party code, a new persistence store, or a second MCP registry.

## Intended files / fence
- `gateway/plugin_registry.py`
- `gateway/app.py`
- `gateway/routes/integrations.py`
- `tests/test_plugin_registry.py`
- `tests/test_integrations_routes.py`

This is a deliberate edit-only fence: the executable objective says `creates no new files` If a new module/test becomes necessary, stop and revise the manifest first.

## Acceptance criteria
1. Production startup has one explicit, idempotent plugin bootstrap path or an explicit no-plugins-supported projection; the registry is no longer accidentally empty.
2. A plugin availability probe failure is represented truthfully with a reason instead of silently omitting the plugin.
3. Enable/disable settings continue to use the existing Kitty DB persistence and cannot enable an unknown plugin name.
4. No arbitrary third-party Python module is imported/executed merely because a file appears on disk.
5. MCP server aggregation continues to come from the existing registry/bridge and no second MCP authority is created.
6. Tests prove repeated startup/bootstrap does not duplicate definitions.

## Verification
**Tier 1 — Builder mechanical.** These are the only commands Builder runs:
- `python -m pytest -q tests/test_plugin_registry.py tests/test_integrations_routes.py`
- `python -m ruff check gateway/plugin_registry.py gateway/routes/integrations.py tests/test_plugin_registry.py tests/test_integrations_routes.py`

**Tier 2 / Tier 3.** Tier 2: live `/plugins` + `/mcp/servers` inspection with one available and one unavailable fixture/built-in where current product truth supports them. Tier 3 required only if Settings UI changes.

Current-green tests are baseline only. The implementation must add or strengthen at least one regression that fails on `70c15583a6afa4aac9a6f6eb11abf840afa377a4` for the verified finding before production edits.

## Failure modes that must be tested
- The original review reproduction is a required RED case, not prose-only evidence.
- Dependency/service unavailable paths stay truthful; UNKNOWN never becomes success.
- Cancellation/timeout/partial input cannot leave a false success receipt.
- The fix must preserve the existing security/authority boundary named in the objective.

## Stop condition
If making plugins useful requires a new dynamic package format/execution sandbox, stop. This packet only makes the existing trusted built-in abstraction real/truthful.

## Recovery / restartability
Registry definitions are process memory plus existing settings rows. Startup must be idempotent and failure-isolated.

## Dedupe / ownership guard
Before activation, re-read `workspace_global`, GitHub issue #490, current Git/PR state, and Builder task ownership. If current `main` already contains an equivalent fix or another live lane owns any implementation path, stop and reconcile rather than creating competing work. This packet never authorizes push, PR creation, merge, paid spend, credential mutation, or edits under `data/`.
