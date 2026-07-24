# Lessons — July 23, 2026 Session

## L-01: Builder free workers fail silently
Free workers (OpenCode ladder) repeatedly hit infra errors on lease reconciliation, env setup, and worktree creation. Running `./kitty builder initiative run --free` rarely completes. **Rule: build manually when the initiative is <10 packets; reserve Builder for unattended overnight runs.**

## L-02: Builder actions are stubs by default
The KX-05 worker generated 5 action files that logged "cancelled task" / "paused initiative" without actually calling the CLI. **Rule: after any Builder worker delivers code, grep for `subprocess` or `import subprocess` — if absent, the action is a stub.**

## L-03: Expert swarm reviews surface consensus issues
Running 6+ expert perspectives (UX, visual, perf, mobile, a11y, onboarding) on the same UI identified 8 unanimous findings. **Rule: before shipping major UI changes, run an expert swarm review. The skill is at `.agents/skills/expert-swarm/SKILL.md`.**

## L-04: Test fixtures break on duplicate text
Adding a new component that renders the same text as an existing one causes `getByText` failures. **Rule: when a test fails with "Found multiple elements", check for duplicate text rendering in new components.**

## L-05: Git push needs `env -u GITHUB_TOKEN`
A stale `GITHUB_TOKEN` env var shadows keyring auth. **Rule: always `env -u GITHUB_TOKEN git push` in this repo.**

## L-06: `.git/index.lock` blocks operations
Killed builder processes can leave stale index locks. **Rule: always `unlink .git/index.lock` before git operations if stash/commit fails.**

## L-07: View router whitelist must stay in sync with surface registry
`useViewRouter.ts` had a hardcoded valid-view list that excluded `'work'` and `'library'` — the entire 7-surface rail silently broke, showing wrong content on 3 surfaces. **Rule: any new ViewId added to `views.ts`/`RAIL_VIEWS` must also be added to `useViewRouter`'s valid list. Better: derive the valid list from `RAIL_VIEWS` / `REDIRECTS` keys instead of maintaining a separate hardcoded list.**

## L-08: VIEWS registry `component` field metadata-only until proven otherwise
Every entry mapped to `HomeState` — the field was metadata (never used for rendering, real rendering in ViewBody switch), but misleading to anyone reading it. **Rule: metadata fields should be either accurate or explicitly marked as metadata-only with a comment.**

## L-09: Signal dismiss must call `signal_store.mark_processed`
The frontend dismiss button called `/repairs/dismiss` which proposed+executed a generic action queue entry — but never touched `signal_store`. Dismissed signals would reappear on next poll. **Rule: any dismiss/acknowledge button in the UI must trace through to the actual store mutation. Test end-to-end: dismiss, refresh, confirm gone.**

## L-10: `log_chat_trace` token-log timestamps can be ISO strings
The token log (`data/kitty_token_log.jsonl`) stores `ts` as ISO-8601 strings, not epoch floats. Any code reading the log for time-based filtering needs a `_parse_ts` helper that handles both. **Rule: when adding time-filtered reads of any JSONL log, always check the actual datatype of the timestamp field before comparing against floats.**

## L-11: Agent-browser snapshots flag UI bugs automated tests miss
The browser snapshot found: 3 surfaces showing wrong content (routing bug), 2 duplicate retry buttons (error state rendering), unlabeled button (mark point). None caught by unit tests. **Rule: before shipping UI changes, run `agent-browser snapshot -i` on all surfaces — 30 seconds, catches more than 100 unit tests.**

## L-12: Browser-injected buttons (Next.js Dev Tools, "issues overlay") are not our code
The snapshot showed "Open Next.js Dev Tools", "Open issues overlay", "Collapse issues badge" — these are injected by Next.js dev mode and browser extensions. **Rule: before flagging UI bugs from an accessibility snapshot, verify the element is in the source, not injected by tooling.**

