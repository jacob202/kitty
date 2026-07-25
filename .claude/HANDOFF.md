# Handoff — 2026-07-25 — gateway-packages (builder collision resolved, suite unverified)

<!-- kitty-handoff
{
  "schema_version": 1,
  "updated_at": "2026-07-25T16:40:00Z",
  "head_sha": "4dfbd96",
  "branch": "gateway-packages",
  "worktree": ".",
  "status": "valid",
  "completed_items": [
    "5c01d6f: repointed 106 stale imports across 65 files at the gateway subpackages; branch went from 0 tests collectible to 2909 passing",
    "4dfbd96: resolved the gateway/builder.py vs gateway/builder/ module-package collision; api.py + projection.py, no compatibility shim",
    "Found and fixed two silent failures from the subpackage move: RESOURCE_MAP prefix and _BUILDER_DESCRIPTION_PATHS",
    "Repointed test_context_assembler.py memory path guards without weakening any assertion",
    "Swept repo-wide for both collision classes — clean"
  ],
  "blockers": [
    "Final full-suite result was never observed — the run was still in flight at session end"
  ],
  "next_action": "Run `python3.12 -m pytest tests/ -q` once and compare against the last known numbers (2909 passed / 20 failed / 29 errors at 5c01d6f). The 29 errors and 4 of the failures should be gone. Anything still failing is either pre-existing or new — check against the list below before assuming.",
  "invalidation_conditions": [
    "HEAD changes beyond 4dfbd96",
    "branch changes off gateway-packages"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

## State

`gateway-packages` at `4dfbd96`. Two commits this session, both runtime repair.

The branch arrived broken: five subpackage moves (builder, memory, image, voice,
stores) had relocated 45 modules and updated zero importers, so `pytest` failed
collection with 75 errors and nothing ran. That is fixed.

## What is verified

- Every gateway module imports — `pkgutil.walk_packages`, 0 failures.
- 298 targeted tests pass across every area touched by `4dfbd96`.
- Both collision classes sweep clean repo-wide: no `module.py` shadowed by a
  same-named package, no package `__init__` exporting a name that is also a
  submodule.
- `llm_client` is not dragged in by `import gateway.builder.<anything>`.

## What is NOT verified

**The final full suite.** It was ~3 minutes into a ~15 minute run when the
session ended. Its result was never seen. Do not assume green.

Last observed full-suite numbers were at `5c01d6f`, *before* the collision fix:
**2909 passed, 20 failed, 29 errors.**

Expected to be fixed by `4dfbd96`:
- 29 errors in `test_integrations_routes.py` (builder shadowing)
- 4 failures in `test_builder.py` (same)
- 2 failures in `test_context_assembler.py` (moved memory paths)

## Known pre-existing failures — not caused by either commit

- `tests/test_check_continuity_state.py` — 4 failures. `.claude/STATE.md` is
  stale against HEAD, so the STATE/HANDOFF agreement check fails on
  `head_sha`, `branch`, `next_action`. Verified identical before and after the
  HANDOFF edit by stashing it and re-running. **Deliberately not fixed** —
  Jacob's instruction was to keep continuity-document cleanup out of the runtime
  repair. This handoff update will not fix it either; STATE.md still describes
  the older `main`@`10bebdd` workstream.
- `scripts/audit_helpers/audit_22_{split,2nd_cut}.py` do not parse — shell
  interpolation pasted into Python. Pre-dates all of this.

That leaves roughly 14 of the 20 failures unattributed. They were never
individually diagnosed. Do not assume they are pre-existing.

## Design notes for whoever picks this up

`gateway.builder` is the package. `gateway/builder/api.py` is the autonomous
build pipeline; its public API is re-exported from `__init__.py` with an explicit
`__all__`, so `from gateway.builder import start` and `builder.status(...)` work
unchanged. That is the `/build` route contract in
`gateway/routes/integrations.py` and 6 monkeypatch targets.

`gateway/builder/projection.py` is the read-only projection that used to be
`builder_status.py`. It was renamed because a `status` submodule and a `status()`
export cannot share the parent attribute — whichever imported last would win.

`source="builder_status"` in `runtime_manifest.py` is deliberately still called
that. It is a wire value the frontend carries in fixtures, and it belongs to a
family of subsystem labels (`source="builder_queue"`), not module paths.

## Do not touch

- `docs/contract-migration.md` and `docs/POLISH_HANDBOOK_2026-07-25.html` are
  untracked and belong to other concurrent workstreams. Both appeared mid-session.
- Docstrings in ~15 test files still name pre-move paths
  (`gateway/builder_loop.py` etc). Prose only, no functional effect. Left alone
  to keep the repair commits scoped.
