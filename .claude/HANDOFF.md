<!-- kitty-handoff
{
  "schema_version": 1,
  "updated_at": "2026-07-27T00:00:00-06:00",
  "head_sha": "78571d2b9e7eace0297a591eecb388b82539b6d9",
  "branch": "main",
  "worktree": ".",
  "status": "invalid",
  "completed_items": [
    "#158 SSRF + path traversal fixed and committed (5490900)",
    "#160 memory persistence fixed and committed (9d6b841)",
    "Committed scripts/session_end_survey.sh (78571d2)"
  ],
  "blockers": [
    "#158 UI 0.0.0.0/tailnet exposure + proxy gateway-secret need Jacob/Codex sign-off"
  ],
  "next_action": "none",
  "invalidation_conditions": [
    "HEAD changes outside a checkpoint commit",
    "branch or worktree changes",
    "active mission changes",
    "pull request state changes"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

# HANDOFF

## What was done this session (2026-07-27)

- Swept oldest open issues in `jacob202/kitty` (confirmed namespace via `gh repo list`; all `gh` calls used `env -u GITHUB_TOKEN` to dodge a stale ambient PAT).
- **#158 (SSRF + path traversal, T2) — FIXED & committed** (`5490900`).
  - `gateway/routes/capture.py`: local capture paths must resolve inside approved roots (DATA_DIR, captures, desktop, knowledge/inbox) else 403.
  - `gateway/routes/knowledge.py`: block private/loopback/link-local/metadata IPs and non-http(s) schemes; manually follow redirects with per-hop re-validation (`MAX_REDIRECTS=5`).
  - Added regression tests: path restriction, traversal, SSRF (localhost/metadata/non-http), and redirect-to-private-IP blocking. 30 tests pass (test_capture + test_knowledge_routes).
  - **Left for Jacob/Codex sign-off (per issue body):** UI `dev:tailnet` 0.0.0.0 bind exposure and proxy gateway-secret injection (`gateway/kitty-chat/src/app/proxy/[...path]/route.ts`). Default `next dev` is 127.0.0.1 — safe.
- **#159 (failed workers report completion, T2) — already fixed in code** at `f1ca471` ("fix(builder): preserve worker failure states"), with passing tests (`test_llm_failure_finishes_agent_as_failed`, `test_stop_cancels_registered_agent_task`, `test_execute_records_failed_when_worker_raises`). Recommend closing as stale-vs-code.
- Committed `scripts/session_end_survey.sh` (user-added to the commit; was untracked/pre-existing).

## In-flight / next move

- **PR #278 CI re-run triggered** (`gh run rerun 30237737266` → new run `30238785944`, in_progress) after confirming the `pytest` regression was already fixed upstream at commit `ddb2537` ("make the receipts store redirectable and isolate it in tests"). Earlier failing check was against stale commit `aeaea53`.
- #161 (e2e move-in test) is the next actionable bug after the #158/#160 security/memory sweep.
- #127 (KittyBuilder queue) is a standing workflow command — likely stale, verify before acting.
- #270 / #274 are newer initiatives already in flight (see kb NOW.md).

## Blockers

- None technical. #158's LAN/tailnet exposure + proxy secret need human sign-off before fully closing.

## Files changed

- `gateway/routes/capture.py` (path allow-list) — committed 5490900
- `gateway/routes/knowledge.py` (SSRF + redirect re-validation) — committed 5490900
- `tests/test_capture.py` (+2 regression tests) — committed 5490900
- `tests/test_knowledge_routes.py` (+6 SSRF tests, FakeStreamResponse fix) — committed 5490900
- `scripts/session_end_survey.sh` — committed 78571d2
- `gateway/memory.py` (session consolidation log) — committed 9d6b841
- `tests/test_memory.py` (+2 persistence tests) — committed 9d6b841
