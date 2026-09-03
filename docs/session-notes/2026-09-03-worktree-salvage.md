# Worktree salvage — 2026-09-03

This note records durable material recovered before retiring stale Kitty/Orca worktrees.

## Preserved backlog artifacts

- `kitty-jacob-decisions-20260831-v1.json` was valid but never applied. Its two backend packets remain backlog, not active Builder ownership.
- `KT-BACKUP-UI-01.md` and `KT-CHAT-TOOLS-01.md` were never landed. Current main still has no Backup UI and no HTTP MCP invocation route, so the product gaps remain real.
- `CODEX_HANDOFF_20260831.md` preserves the dependency/order rationale for those frontend packets. Its dated execution details must be revalidated before use.
- The Agent Context & Runtime Platform design/implementation plan was uncommitted planning work. Its 2026-09-01 baseline is historical; revalidate model/harness versions and already-landed PR references before execution.

## Not preserved as product work

- GAR scope-key test scratch was not copied because the canonical continuity plan already specifies that test and the scope-key implementation itself has not landed.
- WOW acceptance probes, PR review receipts, `.claude/accept-task.md` files, stale `.claude` state, and superseded UI diffs are evidence/scratch, not missing product changes.
- Old Orca supervisor merge-reconciliation work is being ported separately on this branch with fresh tests against current Builder code rather than cherry-picking stale production code verbatim.
