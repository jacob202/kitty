# Review packet: sharded adversarial review, step zero (REVIEW ONLY — no code changed)

## Provenance
- Source: pasted "Sharded adversarial code review — 2026-09-17" (10 shards, ~107 files, 48 findings).
- Recovered: all 10 per-shard JSONs at `/tmp/claude-501/-Users-jacobbrizinnski/c6571ce1-459d-46ed-b999-2c437f60ef81/scratchpad/review-findings/shard-{A..J}.json` (47 findings, keys: file/line/severity/claim/evidence/category).
- NOT recovered: the "failing tests written" for the top 5 — no test files exist anywhere reachable (repo, /tmp, ~/kb, sibling checkouts, room). They must be rewritten; doing so doubles as verification.
- Worktree `.worktrees/adv-fix-20260917` (branch `fix/adv-scope-backup-gate-20260917`, base `8fe538f4`) exists with an active path claim, but zero mutations were made.

## Independent spot-checks (all against origin/main 8fe538f4)

| # | Claim | Verdict |
|---|-------|---------|
| 1 | Sync `call_llm` (httpx.post + time.sleep) called from async `_poll_single_expert` via `_is_duplicate_signal`, no `to_thread` | SHAPE CONFIRMED (`expert_proactive.py:97,220,411`; `llm_client.py:192,625,900`) |
| 2 | `RISK/IRREVERSIBLE_PATTERNS` miss `kitty_backup.py`, `packet_preflight.py` | CONFIRMED (`pr_scope.py:42-97` lists `pr_*`/`purge_*` only) |
| 3 | `idx_runs_one_active_per_task` has no reaper; `last_heartbeat_at` unread | SHAPE CONFIRMED (index + single heartbeat mention in `builder_queue_db.py`); repo-wide heartbeat readership still to check |
| 4 | Comfy `execute()` narrow except lets `OSError` from `write_bytes` escape | SHAPE CONFIRMED (except at ~644, `write_bytes` at 497/705 via `_download_outputs` at 673); exact try-boundaries need a structural check |
| 5 | Global staged attachments leak across chats on switch | CONFIRMED (`KittyContext.tsx:568` clears context refs, not attachments; upload binds `conversationId` at line ~807, send attaches staged ids later) |
| +1 | `pr_review_gate.py` reject-then-approve same-head stays blocked | CONFIRMED from previously read code (blocking scan precedes approval check, no recency) |

## Not yet verified
- The 17 high/critical summaries and 33 medium/low findings beyond the lines pasted (full text is in the shard JSONs).
- Whether any finding duplicates already-tracked work (open PRs/branches were not yet cross-checked file-by-file).
- The #898 follow-up plan (5 gate-hardening findings) is parked until this review is dispositioned.

## Proposed execution (requires reviewer go-ahead; one PR per fix)
1. Rewrite the 5 failing tests; each must FAIL on current main (proof) then PASS after the fix.
2. Fix order: (2) scope patterns, (1) thread offload, (5) per-chat attachments, (3) heartbeat reaper, (4) comfy handler — then the high batch from the shard JSONs.
3. Each PR: regression test + narrowest local checks + CI green; merges only on Jacob’s explicit approval.

## Reviewer: please confirm
- [ ] The 6 verification verdicts above are fairly stated.
- [ ] Fix order is acceptable (or re-order).
- [ ] Execution (steps 1-2) may proceed.
