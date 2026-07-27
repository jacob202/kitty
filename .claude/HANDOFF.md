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

- **#160 (memory persistence, T1/T2) — NOT started.** Inspect `gateway/memory.py`, `gateway/memory_consolidation.py`, `gateway/dream_insights.py`; the insight-storage path may be a no-op. This is the next actionable bug after #158.
- #161 (e2e move-in test) depends on #160.
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
