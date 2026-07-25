# Session Handoff
- Timestamp: 2026-07-25T09:39:12Z
- Session: 3bf8e0d9-d532-4b47-8da9-cfdf04743270
- Original request: Fix `_get_allowed_paths` in `gateway/builder_identity.py` — worker identity verification was reading `initiative_packets.allowed_paths_json` (frozen manifest copy) instead of the live `tasks.allowed_paths_json`, so an operator's post-apply scope correction via `queue edit` would still fail identity verification against stale scope. User was frustrated ("just fix it, no opinion needed") and delegated the fix entirely.
- Current branch: contract-first

## Completed
- [x] `gateway/builder_identity.py:102` — `_get_allowed_paths()` rewritten to `JOIN tasks t ON t.id = ip.task_id` and select `t.allowed_paths_json` instead of reading `initiative_packets.allowed_paths_json` directly. Docstring updated to explain why (matches `builder_runner.py`'s live scope-check source).

## In progress
- [ ] `tests/test_builder_identity.py` — `test_corrupt_or_unbounded_allowlist_fails_closed` (~line 462) currently corrupts `initiative_packets.allowed_paths_json` directly via `UPDATE initiative_packets SET allowed_paths_json = ?`. Since the fix now reads from `tasks.allowed_paths_json` via join, this test's corruption no longer reaches the code path under test and will likely stop failing closed as intended — needs to corrupt `tasks.allowed_paths_json` instead (or in addition). Was mid-investigation of `_apply()` helper (`tests/test_builder_identity.py:51`) and `_valid_identity` fixture (`tests/test_builder_identity.py:261`) to confirm the task/initiative_packets FK relationship before editing the test — not yet done.
- [ ] No test run performed yet against the new join-based implementation.

## Verification status
- Tests: not run this session — unknown pass/fail
- Lint: not run
- Build: not run

## Key decisions
- Identity verification's allowlist check should track the task's live `allowed_paths` (same source as `builder_runner.py`'s runtime scope check), not the immutable manifest snapshot in `initiative_packets`, so operator corrections via `queue edit` are honored.

## Next action
- Update `test_corrupt_or_unbounded_allowlist_fails_closed` to corrupt `tasks.allowed_paths_json` (via the task row linked through `ip.task_id`), then run `python3.12 -m pytest tests/test_builder_identity.py -q` to confirm the fail-closed behavior still holds and no other identity tests broke.
